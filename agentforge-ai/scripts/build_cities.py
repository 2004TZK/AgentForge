#!/usr/bin/env python3
"""生成城市库 app/tools/data/cities.json（面向中国用户，GeoNames 权威数据）。

数据源：GeoNames cities5000（含 >5000 人口城市，字段含经纬度/人口/IANA 时区）。
覆盖：中国大陆 Top 210 城市 + 香港 3 + 澳门 2 + 台湾 8，共 200+ 条。
字段：zh（中文名）/ en（英文名）/ country（中文国家/地区）/ lat / lng / tz（IANA 时区）。

用法：
  python scripts/build_cities.py
"""
import json
import re
import sys
import urllib.request
import zipfile
from pathlib import Path

# 仓库路径
REPO = Path(__file__).resolve().parent.parent.parent
OUT = Path(__file__).resolve().parent.parent / "app" / "tools" / "data" / "cities.json"
ZIP_CACHE = REPO / ".tmp" / "cities5000.zip"
EXTRACT_DIR = REPO / ".tmp" / "cities5000"

GEONAMES_URL = "https://download.geonames.org/export/dump/cities5000.zip"

# 国家代码 → 中文名
COUNTRY_ZH = {"CN": "中国", "HK": "中国香港", "MO": "中国澳门", "TW": "中国台湾"}

# 各地取城市数量
LIMITS = {"CN": 210, "HK": 3, "MO": 2, "TW": 8}

# 兜底中文名（GeoNames alternatenames 缺中文时使用）
FALLBACK_ZH = {
    "Beijing": "北京", "Shanghai": "上海", "Tianjin": "天津", "Chongqing": "重庆",
    "Guangzhou": "广州", "Shenzhen": "深圳", "Chengdu": "成都", "Wuhan": "武汉",
    "Xi'an": "西安", "Xian": "西安", "Hangzhou": "杭州", "Nanjing": "南京",
    "Shenyang": "沈阳", "Qingdao": "青岛", "Jinan": "济南", "Harbin": "哈尔滨",
    "Zhengzhou": "郑州", "Changsha": "长沙", "Kunming": "昆明", "Dalian": "大连",
    "Suzhou": "苏州", "Fuzhou": "福州", "Xiamen": "厦门", "Ningbo": "宁波",
    "Hefei": "合肥", "Wuxi": "无锡", "Nanning": "南宁", "Taiyuan": "太原",
    "Shijiazhuang": "石家庄", "Changchun": "长春", "Lanzhou": "兰州",
    "Guiyang": "贵阳", "Nanchang": "南昌", "Hohhot": "呼和浩特", "Yinchuan": "银川",
    "Urumqi": "乌鲁木齐", "Lhasa": "拉萨", "Xining": "西宁", "Haikou": "海口",
    "Tangshan": "唐山", "Zibo": "淄博", "Xuzhou": "徐州", "Wenzhou": "温州",
    "Yantai": "烟台", "Luoyang": "洛阳", "Handan": "邯郸", "Baotou": "包头",
    "Jilin": "吉林", "Huizhou": "惠州", "Dongguan": "东莞", "Foshan": "佛山",
    "Zhuhai": "珠海", "Zhongshan": "中山", "Jiangmen": "江门", "Shantou": "汕头",
    "Zhanjiang": "湛江", "Guilin": "桂林", "Liuzhou": "柳州", "Quanzhou": "泉州",
    "Zhangzhou": "漳州", "Putian": "莆田", "Yangzhou": "扬州", "Taizhou": "泰州",
    "Nantong": "南通", "Yancheng": "盐城", "Huai'an": "淮安", "Xiangyang": "襄阳",
    "Yichang": "宜昌", "Jingzhou": "荆州", "Hengyang": "衡阳", "Zhuzhou": "株洲",
    "Xiangtan": "湘潭", "Yueyang": "岳阳", "Changde": "常德", "Weifang": "潍坊",
    "Jining": "济宁", "Linyi": "临沂", "Taian": "泰安", "Tai'an": "泰安",
    "Dezhou": "德州", "Liaocheng": "聊城", "Baoding": "保定", "Cangzhou": "沧州",
    "Langfang": "廊坊", "Qinhuangdao": "秦皇岛", "Zhangjiakou": "张家口",
    "Chengde": "承德", "Daqing": "大庆", "Qiqihar": "齐齐哈尔", "Mudanjiang": "牡丹江",
    "Jiamusi": "佳木斯", "Anshan": "鞍山", "Fushun": "抚顺", "Benxi": "本溪",
    "Dandong": "丹东", "Jinzhou": "锦州", "Yingkou": "营口", "Panjin": "盘锦",
    "Chaoyang": "朝阳", "Wuhu": "芜湖", "Bengbu": "蚌埠", "Ma'anshan": "马鞍山",
    "Huaibei": "淮北", "Tongling": "铜陵", "Anqing": "安庆", "Huangshan": "黄山",
    "Chuzhou": "滁州", "Fuyang": "阜阳", "Lu'an": "六安", "Bozhou": "亳州",
    "Xinyang": "信阳", "Nanyang": "南阳", "Kaifeng": "开封", "Xinxiang": "新乡",
    "Jiaozuo": "焦作", "Puyang": "濮阳", "Xuchang": "许昌", "Luohe": "漯河",
    "Sanmenxia": "三门峡", "Anyang": "安阳", "Hebi": "鹤壁",
    "Shangqiu": "商丘", "Zhoukou": "周口", "Zhumadian": "驻马店", "Ganzhou": "赣州",
    "Jiujiang": "九江", "Shangrao": "上饶", "Yichun": "宜春", "Pingxiang": "萍乡",
    "Xinyu": "新余", "Jingdezhen": "景德镇", "Yingtan": "鹰潭", "Nanchong": "南充",
    "Mianyang": "绵阳", "Deyang": "德阳", "Suining": "遂宁", "Guang'an": "广安",
    "Meishan": "眉山", "Leshan": "乐山", "Yibin": "宜宾", "Luzhou": "泸州",
    "Zigong": "自贡", "Neijiang": "内江", "Dazhou": "达州", "Yaan": "雅安",
    "Panzhihua": "攀枝花", "Baoshan": "保山", "Zhaotong": "昭通", "Lijiang": "丽江",
    "Pu'er": "普洱", "Lincang": "临沧", "Qujing": "曲靖", "Yuxi": "玉溪",
    "Chuxiong": "楚雄", "Dali": "大理", "Kashgar": "喀什", "Kashi": "喀什",
    "Hotan": "和田", "Aksu": "阿克苏", "Korla": "库尔勒", "Yining": "伊宁",
    "Shihezi": "石河子", "Karamay": "克拉玛依", "Tacheng": "塔城", "Altay": "阿勒泰",
    "Turpan": "吐鲁番", "Hami": "哈密", "Changji": "昌吉", "Bole": "博乐",
    "Hailar": "海拉尔", "Manzhouli": "满洲里", "Tongliao": "通辽", "Chifeng": "赤峰",
    "Xilinhot": "锡林浩特", "Ordos": "鄂尔多斯", "Bayannur": "巴彦淖尔",
    "Wuhai": "乌海", "Alashan": "阿拉善", "Jiuquan": "酒泉", "Zhangye": "张掖",
    "Wuwei": "武威", "Baiyin": "白银", "Tianshui": "天水", "Pingliang": "平凉",
    "Qingyang": "庆阳", "Longnan": "陇南", "Dingxi": "定西", "Linxia": "临夏",
    "Haixi": "海西", "Yushu": "玉树", "Golog": "果洛", "Hainan": "海南",
    "Wanning": "万宁", "Sanya": "三亚", "Danzhou": "儋州", "Qionghai": "琼海",
    "Wuzhishan": "五指山", "Dongfang": "东方", "Hong Kong": "香港",
    "Kowloon": "九龙", "Tsuen Wan": "荃湾", "Sha Tin": "沙田", "Tuen Mun": "屯门",
    "Macau": "澳门", "Taipa": "氹仔", "Taipei": "台北", "Kaohsiung": "高雄",
    "Taichung": "台中", "Tainan": "台南", "Hsinchu": "新竹", "Keelung": "基隆",
    "Chiayi": "嘉义", "Taoyuan": "桃园", "Pingtung": "屏东", "Hualien": "花莲",
    "Bao'an": "宝安", "Baoan": "宝安", "Changshu": "常熟",
    "Luohu District": "罗湖", "Zhu Cheng City": "诸城",
}

CJK_RE = re.compile(r"[\u4e00-\u9fff]+")


def _ensure_data() -> str:
    """确保数据文件就绪，返回 cities5000.txt 路径。"""
    if not ZIP_CACHE.exists():
        print(f"下载 GeoNames cities5000 → {ZIP_CACHE}")
        ZIP_CACHE.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(GEONAMES_URL, ZIP_CACHE)
    txt = EXTRACT_DIR / "cities5000.txt"
    if not txt.exists():
        EXTRACT_DIR.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(ZIP_CACHE) as zf:
            zf.extractall(EXTRACT_DIR)
    return str(txt)


def _pick_zh(row: dict) -> str:
    """优先 FALLBACK_ZH，其次 alternatenames 中的中文名，最后退回英文名。"""
    ascii_name = row["asciiname"]
    if ascii_name in FALLBACK_ZH:
        return FALLBACK_ZH[ascii_name]
    for token in row["alternatenames"].split(","):
        if CJK_RE.fullmatch(token):
            return token
    return ascii_name


def main() -> int:
    txt = _ensure_data()
    rows = []
    with open(txt, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 19:
                continue
            rows.append(
                {
                    "name": parts[1],
                    "asciiname": parts[2],
                    "alternatenames": parts[3],
                    "lat": float(parts[4]),
                    "lon": float(parts[5]),
                    "country": parts[8],
                    "population": int(parts[14] or 0),
                    "tz": parts[17],
                }
            )

    result: list[dict] = []
    missing_zh: list[str] = []
    for country, limit in LIMITS.items():
        candidates = [r for r in rows if r["country"] == country and r["tz"]]
        candidates.sort(key=lambda r: r["population"], reverse=True)
        # 按英文名去重（同名保留人口最大的）
        seen: set[str] = set()
        picked = []
        for r in candidates:
            key = r["asciiname"].lower()
            if key in seen:
                continue
            seen.add(key)
            picked.append(r)
            if len(picked) >= limit:
                break
        for r in picked:
            zh = _pick_zh(r)
            if zh == r["asciiname"]:
                missing_zh.append(r["asciiname"])
            result.append(
                {
                    "zh": zh,
                    "en": r["name"],
                    "country": COUNTRY_ZH[r["country"]],
                    "lat": round(r["lat"], 4),
                    "lng": round(r["lon"], 4),
                    "tz": r["tz"],
                }
            )

    if missing_zh:
        print(f"⚠ {len(missing_zh)} 条缺少中文名（已退回英文名），可补 FALLBACK_ZH：")
        for name in sorted(set(missing_zh)):
            print(f"    {name}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"✓ 已生成 {OUT}")
    print(f"  城市总数: {len(result)}（中国 {sum(1 for r in result if r['country'] == '中国')}"
          f" / 香港 {sum(1 for r in result if r['country'] == '中国香港')}"
          f" / 澳门 {sum(1 for r in result if r['country'] == '中国澳门')}"
          f" / 台湾 {sum(1 for r in result if r['country'] == '中国台湾')}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
