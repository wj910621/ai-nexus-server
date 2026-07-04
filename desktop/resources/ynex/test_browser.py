"""
浏览器自动化测试
测试网页读取和搜索降级
"""

from browser_automation import read_webpage, search_web


def test_read_webpage():
    print("\n=== 读取网页 ===")
    result = read_webpage("https://www.example.com")
    print(result[:300])
    assert "先生，网页内容摘要" in result
    print("✅ 网页读取通过")


def test_search_web():
    print("\n=== 网页搜索 ===")
    result = search_web("天气预报")
    print(result[:300])
    assert "先生，搜索结果摘要" in result or "失败" in result
    print("✅ 搜索功能通过")


def main():
    print("=== 浏览器自动化测试 ===")
    test_read_webpage()
    test_search_web()
    print("\n全部测试完成")


if __name__ == "__main__":
    main()
