import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table
from rich.status import Status
from rich.text import Text
from rich.panel import Panel

from .config import find_project_dir, load_config, save_config, CONFIG_FILENAME
from .models import ProjectConfig
from .scanner import flatten, unflatten, scan_i18n_files, load_translations, save_translations
from .differ import compute_diff
from .executor import run_claude_translation
from .snapshot import load_snapshot, save_snapshot, load_prev_translation, save_prev_translation
from .task import generate_task, write_task_file, parse_result_file
from .writer import merge_and_write

console = Console()
SKILLS_DIR = Path(__file__).parent.parent / "skills"
TRANS_DIR = Path(".trans")
TASK_FILE = "task.json"
RESULT_FILE = "result.json"
CLAUDE_DIR = Path(".claude")
CLAUDE_SKILLS_DIR = CLAUDE_DIR / "skills"
CLAUDE_COMMANDS_DIR = CLAUDE_DIR / "commands"
CACHE_DIR = Path(".trans_cache")
LOGS_DIR = TRANS_DIR / "logs"


def _find_project(project: str) -> Path:
    """查找项目根目录"""
    if project == ".":
        return find_project_dir()
    return find_project_dir(Path(project).resolve())


@click.group()
@click.option("--project", "-p", default=".", help="项目根目录")
@click.pass_context
def cli(ctx, project):
    """trans -- 基于 Claude Code + Skills 的 i18n 翻译引擎"""
    ctx.ensure_object(dict)
    ctx.obj["project"] = Path(project).resolve()


# ─── init ────────────────────────────────────────────────


@cli.command()
@click.option("--source-lang", "-s", required=True, help="源语言代码（如 zh）")
@click.option("--target-langs", "-t", required=True, help="目标语言，逗号分隔（如 en,ja）")
@click.option("--i18n-dir", default="i18n", help="i18n 文件目录")
@click.pass_context
def init(ctx, source_lang, target_langs, i18n_dir):
    """初始化翻译配置"""
    project_dir: Path = ctx.obj["project"]
    config_path = project_dir / CONFIG_FILENAME
    if config_path.exists():
        console.print(f"[yellow]已存在 {CONFIG_FILENAME}，跳过[/yellow]")
        return

    target_list = [lang.strip() for lang in target_langs.split(",")]
    config = ProjectConfig(
        source_lang=source_lang,
        target_langs=target_list,
        i18n_dir=i18n_dir,
    )

    save_config(project_dir, config)
    console.print(f"[green]✓[/green] 创建 {CONFIG_FILENAME}")

    # 创建 i18n 目录和源文件
    i18n_path = project_dir / i18n_dir
    i18n_path.mkdir(parents=True, exist_ok=True)
    source_file = i18n_path / f"{source_lang}.json"
    if not source_file.exists():
        save_translations(source_file, {})
        console.print(f"[green]✓[/green] 创建 {source_file.relative_to(project_dir)}")

    # 创建 .trans_cache
    cache_dir = project_dir / CACHE_DIR
    cache_dir.mkdir(exist_ok=True)
    console.print(f"[green]✓[/green] 创建 {CACHE_DIR}/")

    # 复制 skills 模板
    if SKILLS_DIR.exists():
        skills_target = project_dir / CLAUDE_SKILLS_DIR
        skills_target.mkdir(parents=True, exist_ok=True)
        for skill_file in SKILLS_DIR.glob("*.md"):
            if skill_file.name != "translate.md":
                dest = skills_target / skill_file.name
                if not dest.exists():
                    shutil.copy2(skill_file, dest)
                    console.print(f"[green]✓[/green] 创建 .claude/skills/{skill_file.name}")

    # 创建 /translate 命令
    commands_target = project_dir / CLAUDE_COMMANDS_DIR
    commands_target.mkdir(parents=True, exist_ok=True)
    translate_cmd = SKILLS_DIR / "translate.md"
    if translate_cmd.exists():
        dest = commands_target / "translate.md"
        if not dest.exists():
            shutil.copy2(translate_cmd, dest)
            console.print(f"[green]✓[/green] 创建 .claude/commands/translate.md")

    console.print(f"\n[bold green]初始化完成！[/bold green]")
    console.print(f"下一步：编辑 {i18n_dir}/{source_lang}.json 添加翻译内容，然后运行 [bold]trans translate[/bold]")


# ─── scan ────────────────────────────────────────────────


@cli.command()
@click.pass_context
def scan(ctx):
    """扫描 i18n 文件状态"""
    project_dir = _find_project(ctx.obj["project"])
    config = load_config(project_dir)
    files = scan_i18n_files(project_dir, config)

    if not files:
        console.print("[yellow]未找到任何 i18n 文件[/yellow]")
        return

    source_flat = load_translations(files[config.source_lang])

    table = Table(title="i18n 文件扫描")
    table.add_column("语言", style="bold")
    table.add_column("文件")
    table.add_column("Key 数量", justify="right")
    table.add_column("状态")

    source_keys = set(source_flat.keys())

    for lang, filepath in sorted(files.items()):
        rel_path = filepath.relative_to(project_dir)
        target_flat = load_translations(filepath)
        if lang == config.source_lang:
            status = "[bold]源语言[/bold]"
        else:
            missing = len(source_keys - set(target_flat.keys()))
            extra = len(set(target_flat.keys()) - source_keys)
            parts = []
            if missing:
                parts.append(f"{missing} 缺失")
            if extra:
                parts.append(f"{extra} 多余")
            status = ", ".join(parts) if parts else "[green]完整[/green]"
        table.add_row(lang, str(rel_path), str(len(target_flat)), status)

    console.print(table)


# ─── translate ────────────────────────────────────────────


@cli.command()
@click.option("--source-lang", "-s", default=None, help="覆盖源语言")
@click.option("--target-langs", "-t", default=None, help="指定目标语言（逗号分隔）")
@click.option("--force", is_flag=True, help="全量重翻（忽略增量 diff）")
@click.option("--dry-run", is_flag=True, help="预览待翻译内容，不调用 CC")
@click.option("--raw-events", is_flag=True, help="终端打印 Claude Agent SDK 原始事件 JSON")
@click.pass_context
def translate(ctx, source_lang, target_langs, force, dry_run, raw_events):
    """执行翻译（调用 Claude Code）"""
    project_dir = _find_project(ctx.obj["project"])
    config = load_config(project_dir)

    if source_lang:
        config.source_lang = source_lang
    if target_langs:
        config.target_langs = [l.strip() for l in target_langs.split(",")]

    # 扫描文件
    files = scan_i18n_files(project_dir, config)
    if config.source_lang not in files:
        console.print(f"[red]未找到源语言文件: {config.source_lang}[/red]")
        return
    source_flat = load_translations(files[config.source_lang])

    # 计算每个目标语言的 diff
    diffs = {}
    existing_translations = {}
    for lang in config.target_langs:
        if lang in files:
            target_flat = load_translations(files[lang])
        else:
            target_flat = {}
        snapshot = {} if force else load_snapshot(project_dir, config.source_lang)
        diff = compute_diff(source_flat, target_flat, snapshot)
        diffs[lang] = diff
        existing_translations[lang] = target_flat

        if diff.added or diff.changed:
            parts = []
            if diff.added:
                parts.append(f"{len(diff.added)} new")
            if diff.changed:
                parts.append(f"{len(diff.changed)} changed")
            console.print(f"  {lang}: {', '.join(parts)} ({diff.unchanged} unchanged)")
        else:
            console.print(f"  {lang}: [green]已是最新[/green]")

    # 生成翻译任务
    task = generate_task(config.source_lang, config.target_langs, diffs, existing_translations)

    if not task.tasks:
        console.print("\n[bold green]所有翻译已是最新，无需操作[/bold green]")
        return

    total_keys = sum(len(lt.items) for lt in task.tasks.values())
    langs = list(task.tasks.keys())
    console.print(f"\n待翻译: {total_keys} keys × {len(langs)} 语言 ({', '.join(langs)})")

    if dry_run:
        console.print("\n[bold]--dry-run 模式，预览待翻译内容：[/bold]\n")
        for lang, lang_task in task.tasks.items():
            console.print(f"[bold]{config.source_lang} → {lang}[/bold]")
            for key, value in lang_task.items.items():
                console.print(f"  {key}: {value}")
            console.print()
        return

    # 写入 task.json
    trans_path = project_dir / TRANS_DIR
    trans_path.mkdir(exist_ok=True)
    task_file = trans_path / TASK_FILE
    write_task_file(task, task_file)
    console.print(f"[green]✓[/green] 生成 {task_file.relative_to(project_dir)}")

    # 调用 CC（直接透传终端输出）
    prompt = (
        "请读取 .trans/task.json，使用你的翻译 skills "
        "(terminology、style、domain) 完成所有语言的翻译，"
        "将结果写入 .trans/result.json。"
    )
    console.print(f"\n[bold]调用 Claude Code...[/bold]\n")
    console.print("[dim]执行器: Claude Agent SDK[/dim]")
    console.print(f"[dim]工作目录: {project_dir}[/dim]\n")
    log_file = project_dir / LOGS_DIR / f"{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
    console.print(f"[dim]审计日志: {log_file.relative_to(project_dir)}[/dim]")
    if raw_events:
        console.print("[dim]终端输出: 原始事件 JSON[/dim]")
    console.print()

    try:
        run_claude_translation(
            project_dir,
            prompt,
            console,
            raw_events=raw_events,
            log_path=log_file,
        )
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        return

    # 解析结果
    result_file = project_dir / TRANS_DIR / RESULT_FILE
    if not result_file.exists():
        console.print("[red]CC 未生成 result.json[/red]")
        return

    result = parse_result_file(result_file)

    # 回写翻译
    console.print("\n[bold]回写翻译结果...[/bold]")
    i18n_dir = project_dir / config.i18n_dir
    for lang in config.target_langs:
        if lang not in result.results:
            console.print(f"  {lang}: [yellow]CC 未返回结果[/yellow]")
            continue

        lang_result = result.results[lang]
        filepath = i18n_dir / f"{lang}.json"
        existing = existing_translations.get(lang, {})
        removed = diffs[lang].removed

        count = merge_and_write(filepath, existing, lang_result.translations, removed)
        console.print(f"  {lang}: {count} keys → {filepath.relative_to(project_dir)}")

        # 保存翻译缓存
        merged = {**existing, **lang_result.translations}
        save_prev_translation(project_dir, lang, merged)

    # 保存源文件快照
    save_snapshot(project_dir, config.source_lang, source_flat)
    console.print(f"[green]✓[/green] 快照已更新")

    # 输出 notes
    all_notes = []
    all_missing = []
    for lang, lang_result in result.results.items():
        if lang_result.notes:
            for note in lang_result.notes:
                all_notes.append(f"[{lang}] {note}")
        if lang_result.missing_terms:
            all_missing.extend(lang_result.missing_terms)

    if all_notes:
        console.print(f"\n[bold]Notes:[/bold]")
        for note in all_notes:
            console.print(f"  • {note}")

    if all_missing:
        missing_unique = list(dict.fromkeys(all_missing))
        console.print(f"\n[bold]建议补充术语表:[/bold]")
        for term in missing_unique:
            console.print(f"  • {term}")

    console.print(f"\n[bold green]翻译完成！[/bold green] {total_keys} keys × {len(langs)} 语言")


# ─── validate ────────────────────────────────────────────


@cli.command()
@click.option("--target-lang", "-t", default=None, help="指定校验语言")
@click.pass_context
def validate(ctx, target_lang):
    """校验翻译完整性"""
    project_dir = _find_project(ctx.obj["project"])
    config = load_config(project_dir)
    files = scan_i18n_files(project_dir, config)

    if config.source_lang not in files:
        console.print(f"[red]未找到源语言文件: {config.source_lang}[/red]")
        return
    source_flat = load_translations(files[config.source_lang])

    source_keys = set(source_flat.keys())
    check_langs = [target_lang] if target_lang else config.target_langs

    table = Table(title="翻译校验")
    table.add_column("语言", style="bold")
    table.add_column("缺失", justify="right", style="red")
    table.add_column("多余", justify="right", style="yellow")
    table.add_column("空值", justify="right", style="red")
    table.add_column("总计", justify="right")
    table.add_column("状态")

    for lang in check_langs:
        if lang not in files:
            table.add_row(lang, "-", "-", "-", "-", "[red]文件不存在[/red]")
            continue

        target_flat = load_translations(files[lang])
        target_keys = set(target_flat.keys())
        missing = source_keys - target_keys
        extra = target_keys - source_keys
        empty = {k for k, v in target_flat.items() if not v.strip()}

        # 检查占位符完整性
        import re
        placeholder_re = re.compile(r"\{[^}]+\}|%[sd]")
        placeholder_errors = 0
        for k in source_keys & target_keys:
            src_ph = set(placeholder_re.findall(source_flat.get(k, "")))
            tgt_ph = set(placeholder_re.findall(target_flat.get(k, "")))
            if src_ph != tgt_ph:
                placeholder_errors += 1

        total = len(target_flat)
        has_error = missing or empty or placeholder_errors
        status = "[red]FAIL[/red]" if has_error else "[green]PASS[/green]"

        table.add_row(
            lang,
            str(len(missing)),
            str(len(extra)),
            str(len(empty)),
            str(total),
            status,
        )

    console.print(table)


# ─── status ──────────────────────────────────────────────


@cli.command()
@click.pass_context
def status(ctx):
    """显示翻译进度"""
    project_dir = _find_project(ctx.obj["project"])
    config = load_config(project_dir)
    files = scan_i18n_files(project_dir, config)

    if config.source_lang in files:
        source_flat = load_translations(files[config.source_lang])
        source_count = len(source_flat)
    else:
        console.print(f"[red]未找到源语言文件: {config.source_lang}[/red]")
        return

    table = Table(title="翻译进度")
    table.add_column("语言", style="bold")
    table.add_column("已翻译", justify="right")
    table.add_column("总计", justify="right")
    table.add_column("完成度", justify="right")
    table.add_column("进度条")

    for lang, filepath in sorted(files.items()):
        if lang == config.source_lang:
            table.add_row(lang, "-", str(source_count), "-", "[dim](源语言)[/dim]")
            continue

        target_flat = load_translations(filepath)
        translated = len(set(source_flat.keys()) & set(target_flat.keys()))
        pct = (translated / source_count * 100) if source_count > 0 else 0
        bar_len = 20
        filled = int(bar_len * pct / 100)
        bar = "█" * filled + "░" * (bar_len - filled)

        color = "green" if pct == 100 else "yellow" if pct >= 80 else "red"
        table.add_row(
            lang,
            str(translated),
            str(source_count),
            f"[{color}]{pct:.0f}%[/{color}]",
            f"[{color}]{bar}[/{color}]",
        )

    console.print(table)


if __name__ == "__main__":
    cli()
