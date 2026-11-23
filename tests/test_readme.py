from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_readme_has_one_h1():
    """合并后只能有一个一级标题，否则 GitHub 的目录结构会打架。"""
    lines = read("README.md").splitlines()
    assert sum(1 for line in lines if line.startswith("# ")) == 1


def test_chinese_is_collapsible_and_flat():
    text = read("README.md")
    assert "\n## 简体中文\n" in text
    assert text.count("<details>") == 1
    assert text.count("</details>") == 1
    assert "<summary>" in text

    # 折叠块里的标题必须整体降级过：不能再出现 h1 / h2
    block = text.split("## 简体中文", 1)[1]
    for line in block.splitlines():
        assert not line.startswith("# "), line
        assert not line.startswith("## "), line


def test_zh_readme_is_a_pointer():
    lines = read("README.zh-CN.md").splitlines()
    assert len(lines) < 25, len(lines)
    assert "README.md#简体中文" in "\n".join(lines)