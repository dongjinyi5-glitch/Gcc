# -*- coding: utf-8 -*-
"""章节 -> 历史原型。权威来源是 docs/CHAPTERS.md，这里只是它的代码形态。

为什么要单独一个模块：`SCENE_PLAN.md` 里第一版的历史标签是**按美术猜的**，后来用
mainData 的 build settings 场景表 + 12 张章节卡贴图核准，发现 L3/L4/L5/L8/L13/L14
六关写错了。表格里如果继续用错的标签，用户会拿错的期望去审图。

所以这里只放**已核准**的那一套，并且每个值都能在 CHAPTERS.md 找到出处。
"""

# level -> 章节信息
#   cn      中文章节名（游戏章节选择界面显示的，用户要求全程用这个）
#   card    卡面标题（12 张 800×500 章节卡上的标题）
#   scene   场景文件（level 对应的 .unity 名，用来核对）
#   hist    历史原型
#   date    时间
#   intent  这一关要变成什么样 —— 一句话，给重绘当验收标准
#   strength 形态吻合度：极强/很强/强/中/弱。弱的那几关要提前说清楚，不能硬套
CHAPTERS = {
    "level0": dict(cn="主菜单", card="（动态菜单，无卡）", scene="MainMenu",
                   hist="滇缅公路雨季 · 行军纵队", date="1942",
                   intent="雨雾里的公路剪影：卡车车队、骡马、斗笠兵，远处山脊",
                   strength="中"),
    "level3": dict(cn="轮船", card="到达即死亡", scene="boat",
                   hist="伊洛瓦底江运兵船 · 撤退渡江", date="1942.4",
                   intent="把黑帮游船改成运送远征军的江轮：铆接钢板、运兵舱、担架与枪架",
                   strength="很强"),
    "level4": dict(cn="暴徒镇港口", card="战争码头", scene="harbour",
                   hist="仰光港（英军撤离前）", date="1942.3",
                   intent="栈桥、门吊、仓库雨棚不变，堆上撤离物资：油桶、板条箱、缆桩",
                   strength="极强"),
    "level5": dict(cn="市郊", card="仓库暴乱", scene="harbourPart2",
                   hist="仰光码头区后段 · 仁安羌物资转运", date="1942.4",
                   intent="船坞吊车群 + 待运油桶列 + 铁轨，港区纵深而不是市郊街道",
                   strength="很强"),
    "level6": dict(cn="暗黑小巷", card="一夜肢解", scene="alleyStreets",
                   hist="腾冲古城街巷", date="1942.5 沦陷 / 1944 攻城",
                   intent="火山石墙、木构铺面、门楣匾额、马灯，替换砖墙与绿门",
                   strength="很强"),
    "level7": dict(cn="博尼诺的脱衣舞夜总会", card="干净利索！", scene="stripclub",
                   hist="曼德勒英军俱乐部（插叙）", date="1942.4",
                   intent="布局不动，改成后方俱乐部：木吧台、吊扇、军旗、藤椅",
                   strength="弱"),
    "level8": dict(cn="军团据点", card="乔尼，拿起你的枪！", scene="bridge",
                   hist="惠通桥东岸桥头堡", date="1942.5.4",
                   intent="石阶铁栏换成桥头堡碉楼：沙袋、铁丝网、探照灯架、机枪巢",
                   strength="很强"),
    "level9": dict(cn="河流", card="遥远的桥", scene="brokenBridge",
                   hist="惠通桥 1942.5.5 炸桥", date="1942.5.5",
                   intent="怒江峡谷里的单孔钢桁桥，桥面断口、坠江桥板、盘山公路",
                   strength="极强"),
    "level10": dict(cn="下水道", card="追逐白日梦", scene="sewers",
                    hist="松山日军坑道工事", date="1944.7",
                    intent="砖砌暗渠换成原木支护坑道：弹药箱、电话线、油灯",
                    strength="强"),
    "level11": dict(cn="存储器", card="大智若愚", scene="sewersPart2",
                    hist="松山子高地坑道药室 · 蓄水池", date="1944.8",
                    intent="蓄水池与竖井保留形制，加爆破药室、导火索、渗水岩壁",
                    strength="强"),
    "level12": dict(cn="选择标签栏", card="月光屠杀", scene="secretLab",
                    hist="日军地下指挥所 · 战俘营", date="1944.8",
                    intent="铁网探照灯换成地下指挥所：通信电缆、铁栅、地图桌",
                    strength="中"),
    "level13": dict(cn="建筑工地", card="有很长的路要走", scene="constructionSite",
                    hist="修筑中印公路 · 惠通桥抢修", date="1944",
                    intent="脚手架跳板不动，改成桥墩基坑、混凝土搅拌、GMC 卡车",
                    strength="强"),
    "level14": dict(cn="屋顶", card="圣诞老公公来了", scene="rooftops",
                    hist="密支那机场 · 飞虎队 P-40", date="1944.8",
                    intent="屋顶换成机场塔台与机库顶；飞艇要改轮廓成停机坪上的 C-46",
                    strength="弱"),
}

# 章节顺序（游戏里的先后），表格按这个排
ORDER = ["level0", "level3", "level4", "level5", "level6", "level7",
         "level8", "level9", "level10", "level11", "level12", "level13", "level14"]

# 用户已确认排除的两个范围（见 SHOT_LIST.md 的 CLOSED 段）
CLOSED = [
    ("船体外观全景",
     "游戏内每屏都是局部视角，整条船无法一次入画",
     "不需要 —— 原生全景贴图 7000×1018 本来就含整条船，比任何截图完整"),
    ("驾驶室 / 舵轮",
     "本关没有这一间",
     "Wheelhouse_01 贴图存在，但它是船体外观件，不是可进入的房间"),
]


def hist_of(level):
    return CHAPTERS.get(level, {}).get("hist", "—")


def cn_of(level):
    return CHAPTERS.get(level, {}).get("cn", level)


def describe(levels):
    """一个构件可能横跨多关，历史原型要按关列出并去重。"""
    seen, out = set(), []
    for lv in levels:
        h = hist_of(lv)
        if h not in seen:
            seen.add(h)
            out.append("%s：%s" % (cn_of(lv), h))
    return "；".join(out)
