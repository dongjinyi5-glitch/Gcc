"""One place that decides what a scene component *is*.

Two axes, both needed by the component table:

* 类别 -- the art-side grouping an art director reviews by ("船体与船舱",
  "码头与栈桥").  A reviewer should not have to read 1450 English names.
* 图层 -- what the row belongs to *in the pipeline*: 背景 is what this project
  replaces; 角色部件 / 武器 / UI / 特效 are handled by other passes and only
  appear in the table so the picture is complete.

Rules are ordered regexes, first match wins, so the specific must come before
the general: `WallConstructionTile` is 建筑工地, not 街巷外墙, and `BoatReling`
is 船体, not 栏杆.  Anything unmatched lands in 未分类 and is printed, never
silently bucketed -- an unclassified component is a component nobody will
remember to replace.

Dutch names (`Romp` hull, `Buizen` pipes, `Steiger` jetty, `Ruim` hold, `Muur`
wall, `Reling` railing, `Ketel` boiler, `Luik` hatch) are not typos: the art was
outsourced to a Dutch studio and the source names stuck.
"""
import re

# levelN -> the chapter name the user reads on the chapter-select screen
LEVEL_CN = {
    "level0": "主菜单",
    "level3": "轮船",
    "level4": "暴徒镇港口",
    "level5": "市郊",
    "level6": "暗黑小巷",
    "level7": "博尼诺的脱衣舞夜总会",
    "level8": "军团据点",
    "level9": "河流",
    "level10": "下水道",
    "level11": "存储器",
    "level12": "选择标签栏",
    "level13": "建筑工地",
    "level14": "屋顶",
}

# Order matters.  (类别, 图层, regex) -- first match wins.
RULES = [
    # ---- 另案：不进背景替换流程 -------------------------------------------
    ("彩蛋", "背景", r"^(r2d2|cannoli|trex|easteregg)"),
    ("角色部件", "角色", r"^(head|armfront|armback|armlow|leglow|legup|torso|hand|"
                     r"foot|neck|crotch|hat$|bodyonball|gang|goon|"
                     r"frankieeyes|vinniehealth|actionpump|01stoel)"),
    ("武器", "武器", r"^(tommygun|shotgun|magnum|lupara|bazooka|flamethrower|"
                  r"teslacoilgun|grenade|molotov|dynamite|boxhandgrenades|"
                  r"boxmolotovs|handammoclip|maximgun|maxigunmg|vickersgun|"
                  r"mortar|gunholder)"),
    ("界面与章节卡", "UI", r"^(startscreen|hudatlas|menuatlas)"),

    # ---- 背景：按视觉体量从大到小 -----------------------------------------
    ("船体与船舱", "背景", r"^(boat|romp|ledgeship|ledge-cargoship|wheelhouse|"
                       r"propellor|ship-|shipdistance|supportbeam-ship|pipeboat|"
                       r"doorship|lifeboat|sloop|brokensloop|ruim|luik)"),
    ("建筑工地", "背景", r"^(scaffold|conctrete|construcion|wallconstruction|"
                      r"buildingfloor|metalconstruction|wreckingball|"
                      r"doorconstruction)"),
    ("下水道与竖井", "背景", r"^(sewer|subway|shafts|2ndshafts|gutter|manhole|"
                        r"lightmanhole|squarehole|elevatorshaft|elevatorbar|"
                        r"elevatorbottom|elevatortop|elevatorroom)"),
    ("尸体与残骸", "背景", r"^(deadzombie|garagezombie|lijk|floatingcorpse)"),
    ("蓄水池与水面", "背景", r"^(waterreservoir|waterrervoir|watertower|water|"
                        r"carunderwater|woodinwater|wagoninwater)"),
    ("屋顶与飞艇", "背景", r"^(roof|zeppelin|airco|chimney|tower)"),
    ("桥梁与桥头堡", "背景", r"^(bridge|fullbridge|metalbridge)"),
    ("天空与月亮", "背景", r"^(sky|moon)"),
    ("港口远景层", "背景", r"^(harbour-background|harbour_background|"
                       r"harbourparallax|cityparallax|outskirtsparallax|"
                       r"racineavenue|riverside)"),
    ("码头与栈桥", "背景", r"^(quay|steiger|harbour|platform|pilebags|pilebricks|"
                       r"pallets|pallet|crane|bigcrane|ballcrane|hook|"
                       r"anchor|reling|railing|paaltje|ballustrade|balustrade|"
                       r"polebrick)"),
    ("车辆与载具", "背景", r"^(car|truck|taxi|police|blackcar|bustedcar|bustedtruck|"
                       r"wagon|train|fuelwagon|wheel|windshield|licenceplate|bustedpolice|"
                       r"headlight|taillight|frontfender|rearfender|carpile)"),
    ("军用工事", "背景", r"^(army|barbedwire|checkpoint|guardhouse|restrictedarea|"
                      r"landmine|gastank|policesiren|obstacletires|barricade)"),
    ("室内空间", "背景", r"^(stripclub|room|oldbuildinginside|belluccio|bar1|bar2|"
                      r"curtain|kitchen|table|chair|couch|shelf|shelves|bed|"
                      r"commode|gramaphone|statue|wallpaper|hangar-insides|frankiechair)"),
    ("货箱麻袋桶", "背景", r"^(crate|bag|baal|barrel|oilbarrel|beercrate|boxes|"
                       r"container|bustedcontainer|dumpster|garbage|planks|rope|"
                       r"chain|wire|airtubes|hose|hangar-barrelpile|broken-barrel|broken-table|explosive-barrel)"),
    ("管线与钢结构", "背景", r"^(pipe|buizen|buis|gaspipe|metalpipe|metalpilar|"
                        r"metalwall|pilar|peiler|hekwood|ketel|steampot|lever|"
                        r"gasgenerator|luster|cable|cupperbolt|hangarsupport)"),
    ("栏杆楼梯与通道", "背景", r"^(ladder|firestairs|fireescape|stairs|stair|balcony|"
                          r"railbalcony|outsiderailring|passage|portaal|entrance|"
                          r"exit|door|window|gate|fence|schutting|wallfence|"
                          r"outsidewindow)"),
    ("街巷与建筑外墙", "背景", r"^(alley|streetsbackground|wall|building|garage|"
                          r"part|beginwall|endwall|corner|edge|gap|inbetween|"
                          r"floor|middlepiece|backpiece|frontpiece|bustedhangar|"
                          r"oldbuildingoutside)"),
    ("招牌与标识", "背景", r"^(sign|billboard|caution|liveammo|bonninos|"
                       r"belluccioslogo|rustys)"),
    ("灯光与灯具", "背景", r"^(light|lamp|hangar-light|rooftoplight|"
                       r"platform1light|streetlight|lit)"),
    ("街道设施与小道具", "背景", r"^(bottle|glass|phonebooth|firehydrant|"
                            r"fireextingwisher|shovel|pole|legger|kuip|kickbutton|"
                            r"explosivecharges|fueltankflamethrower|secretentrance|electricpole)"),
    ("阴影与遮挡层", "背景", r"^shadow"),
    ("自然物", "背景", r"^(tree|bush|rocks|sand|rubble|ruble|log)"),
    ("特效", "特效", r"^(fireloop|bubb|electricity|water_splash|waterrunning|"
                  r"waterripple|watershine|steam)"),
]

_COMPILED = [(c, l, re.compile(p, re.I)) for c, l, p in RULES]


def classify(texture):
    """-> (类别, 图层).  Unmatched -> ('未分类', '背景') so it shows up loudly."""
    n = texture.lower()
    for cat, layer, rx in _COMPILED:
        if rx.match(n):
            return cat, layer
    return "未分类", "背景"


def levels_cn(levels):
    return "、".join(LEVEL_CN.get(l, l) for l in levels)


def report(inv):
    from collections import Counter
    cat = Counter()
    lay = Counter()
    miss = []
    for r in inv:
        c, l = classify(r["texture"])
        cat[c] += 1
        lay[l] += 1
        if c == "未分类":
            miss.append(r["texture"])
    return cat, lay, miss


if __name__ == "__main__":
    import io
    import json
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from ggc_assets import PROJECT

    inv = json.load(io.open(os.path.join(PROJECT, "art", "scene_inventory.json"),
                            encoding="utf-8"))
    cat, lay, miss = report(inv)
    print("图层:", dict(lay))
    print()
    for k, v in cat.most_common():
        print("%5d  %s" % (v, k))
    print("\n未分类 %d 个:" % len(miss))
    for n in sorted(miss):
        print("   ", n)
