#!/usr/bin/env python3
"""
密卷模考系统 - 授权码生成工具
用法:
  列出可用码:    python encrypt_tool.py list
  生成新授权码:  python encrypt_tool.py gen <客户名> [到期日]
  加密题库:      python encrypt_tool.py enc <题库.json> <输出.enc>
  查看已发:      python encrypt_tool.py status

示例:
  python encrypt_tool.py gen 张三 2026-07-01
  python encrypt_tool.py gen 李四  （默认30天过期）
  python encrypt_tool.py enc 国家电网.json 国家电网.enc
"""

import sys, os, json, hashlib, base64, time
from datetime import datetime, timedelta

# ====== 主密钥（与HTML中一致）========
MASTER_KEY = "MjU0N2NmOTExMmIzNDU2"
CODES_FILE = "issued_codes.json"

def sha256(s):
    return hashlib.sha256(s.encode()).hexdigest()

def generate_code(customer, expiry_date=None):
    """生成唯一授权码"""
    if not expiry_date:
        expiry_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    
    # 验证日期格式
    try:
        datetime.strptime(expiry_date, "%Y-%m-%d")
    except:
        print("日期格式错误，请使用 YYYY-MM-DD")
        return None
    
    # 用客户名+密钥+到期日生成唯一哈希
    raw = f"{MASTER_KEY}:{customer}:{expiry_date}"
    code_hash = sha256(raw)
    
    # 格式: MIJUAN-<客户简写>-<校验码前8位>-<到期日短码>
    # 客户简写: 取客户名拼音/英文前4位或中文前2字
    short = customer[:2] if len(customer) >= 2 else customer
    
    # 到期日短码: base62编码的日期差值(从今天到到期日的天数)
    today = datetime.now()
    exp = datetime.strptime(expiry_date, "%Y-%m-%d")
    days = (exp - today).days
    if days < 0:
        days = 0
    days_code = base64.b64encode(str(days).encode()).decode()[:3].replace('=', 'Z')
    
    verify = code_hash[:6]
    code = f"MJ-{short}-{verify}-{days_code}"
    
    return {
        "code": code,
        "customer": customer,
        "expiry": expiry_date,
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "used": False
    }

def load_issued():
    if os.path.exists(CODES_FILE):
        with open(CODES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_issued(codes):
    with open(CODES_FILE, 'w', encoding='utf-8') as f:
        json.dump(codes, f, ensure_ascii=False, indent=2)

def cmd_gen():
    if len(sys.argv) < 3:
        print("用法: python encrypt_tool.py gen <客户名> [到期日 YYYY-MM-DD]")
        return
    
    customer = sys.argv[2]
    expiry = sys.argv[3] if len(sys.argv) > 3 else None
    
    issued = load_issued()
    
    # 检查是否已经给该客户生成过
    for c in issued:
        if c["customer"] == customer and not c.get("used", False):
            print(f"⚠️ {customer} 已有未使用的授权码: {c['code']}")
            reply = input("重新生成? (y/n): ").strip().lower()
            if reply != 'y':
                return
            # 撤销旧的
            c["used"] = True
            c["revoked"] = True
    
    result = generate_code(customer, expiry)
    if not result:
        return
    
    issued.append(result)
    save_issued(issued)
    
    print("=" * 50)
    print(f"  授权码生成成功")
    print("=" * 50)
    print(f"  客户:     {customer}")
    print(f"  到期:     {result['expiry']}")
    print(f"  授权码:   {result['code']}")
    print()
    print(f"  将此授权码发给客户即可")
    print(f"  已记录到: {CODES_FILE}")
    print("=" * 50)

def cmd_list():
    issued = load_issued()
    if not issued:
        print("暂无已生成的授权码")
        return
    
    print("=" * 60)
    print(f"  已生成授权码 ({len(issued)} 个)")
    print("=" * 60)
    
    unused = [c for c in issued if not c.get("used")]
    used = [c for c in issued if c.get("used")]
    
    if unused:
        print(f"\n📌 未使用 ({len(unused)} 个):")
        for c in unused:
            print(f"  {c['code']}  |  {c['customer']}  |  到期: {c['expiry']}")
    
    if used:
        print(f"\n✅ 已使用/已撤销 ({len(used)} 个):")
        for c in used[:10]:
            print(f"  {c['code']}  |  {c['customer']}  |  {c.get('used_date','?')}")

def cmd_encrypt():
    if len(sys.argv) < 4:
        print("用法: python encrypt_tool.py enc <题库.json> <输出.enc>")
        return
    
    json_path = sys.argv[2]
    output_path = sys.argv[3]
    
    if not os.path.exists(json_path):
        print(f"文件不存在: {json_path}")
        return
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    
    # XOR加密
    key = MASTER_KEY
    data_bytes = json_str.encode('utf-8')
    result = bytearray()
    for i in range(len(data_bytes)):
        result.append(data_bytes[i] ^ ord(key[i % len(key)]))
    
    encoded = base64.b64encode(bytes(result)).decode()
    checksum = sha256(json_str)[:8]
    
    output = {"v": 1, "c": checksum, "d": encoded}
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, separators=(',', ':'))
    
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"✅ 已加密: {output_path} ({size_mb:.1f}MB)")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "gen":
        cmd_gen()
    elif cmd == "list":
        cmd_list()
    elif cmd == "enc":
        cmd_encrypt()
    else:
        print(f"未知命令: {cmd}")
