import argparse
import asyncio
import random
import string
import dns.asyncresolver
from tqdm import tqdm
import sys

# ================== 参数 ==================
CONCURRENCY = 200
TEST_COUNT = 3

resolver = dns.asyncresolver.Resolver()
resolver.lifetime = 3
resolver.nameservers = ["8.8.8.8", "1.1.1.1"]

semaphore = asyncio.Semaphore(CONCURRENCY)

# ================== 工具函数 ==================
def banner():
    print(r"""
 __        ___ _     _  ____ _                  
 \ \      / (_) | __| |/ ___| | ___  __ _ _ __  
  \ \ /\ / /| | |/ _` | |   | |/ _ \/ _` | '_ \ 
   \ V  V / | | | (_| | |___| |  __/ (_| | | | |
    \_/\_/  |_|_|\__,_|\____|_|\___|\__,_|_| |_|

        DNS Wildcard Domain Cleaner
        Author: huangyi
""")

def random_subdomain(domain, length=10):
    rand = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))
    return f"{rand}.{domain}"

async def resolve_A(domain):
    try:
        answers = await resolver.resolve(domain, "A")
        return sorted(r.address for r in answers)
    except Exception:
        return None

async def resolve_CNAME(domain):
    try:
        answers = await resolver.resolve(domain, "CNAME")
        return sorted(str(r.target).rstrip('.') for r in answers)
    except Exception:
        return None

async def is_wildcard(domain):
    async with semaphore:
        base_a = await resolve_A(domain)
        base_cname = await resolve_CNAME(domain)

        if not base_a and not base_cname:
            return False

        for _ in range(TEST_COUNT):
            test_domain = random_subdomain(domain)
            test_a = await resolve_A(test_domain)
            test_cname = await resolve_CNAME(test_domain)

            # A 泛解析
            if base_a and test_a == base_a:
                continue

            # CNAME 泛解析
            if base_cname and test_cname == base_cname:
                continue

            return False

        return True

# ================== 核心执行 ==================
async def run(domains):
    total = len(domains)
    results = []

    tasks = [
        (domain, asyncio.create_task(is_wildcard(domain)))
        for domain in domains
    ]

    for domain, task in tqdm(tasks, desc="泛解析过滤中", ncols=80):
        if not await task:
            results.append(domain)

    with open("result.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(results))

    # ===== 统计输出 =====
    print("\n[✓] 泛解析检测完成")
    print(f"[+] 输入域名总数: {total}")
    print(f"[+] 去除泛解析后剩余域名: {len(results)}")
    print("[+] 结果已保存至 result.txt")

# ================== CLI ==================
def main():
    banner()
    parser = argparse.ArgumentParser(
        description="泛解析过滤工具（支持 A / CNAME）",
        usage="""
示例:
  python wildcard_filter.py -u example.com
  python wildcard_filter.py -f domains.txt
        """
    )

    parser.add_argument("-u", "--url", help="检测单个域名")
    parser.add_argument("-f", "--file", help="读取域名文件（一行一个）")

    args = parser.parse_args()

    if not args.url and not args.file:
        parser.print_help()
        sys.exit(0)

    domains = set()
    webvpn_kept = False

    if args.url:
        if "webvpn" not in args.url.lower():
            domains.add(args.url.strip())

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                for line in f:
                    domain = line.strip()
                    if not domain:
                        continue

                    if "webvpn" in domain.lower():
                        if not webvpn_kept:
                            domains.add(domain)
                            webvpn_kept = True  # 只保留第一个
                        continue

                    domains.add(domain)

        except FileNotFoundError:
            print(f"[!] 文件不存在: {args.file}")
            sys.exit(1)

    asyncio.run(run(list(domains)))

if __name__ == "__main__":
    main()
