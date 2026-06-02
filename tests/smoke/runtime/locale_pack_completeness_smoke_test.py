from __future__ import annotations

from _path_bootstrap import ensure_repo_root

ensure_repo_root(__file__)

import json
import re
from pathlib import Path

from app.data import cards as card_data


ROOT = Path(__file__).resolve().parents[3]
LOCALE_DIR = ROOT / "static" / "locales"
CARDS_JSON = ROOT / "app" / "data" / "cards.json"

NEW_LOCALES = {
    "zh-TW": "zh-TW.json",
    "fr-FR": "fr-FR.json",
    "de-DE": "de-DE.json",
}
FR_DE_LOCALES = ("fr-FR", "de-DE")
CJK_RE = re.compile(r"[\u3400-\u9fff\u3040-\u30ff\uac00-\ud7af]")
ZHT_SIMPLIFIED_RESIDUE_RE = re.compile(
    r"[万与个丛两严丧丰临为举么义乌乐乔习乡书买乱争于亏云亚产亩亲亵亿仅从仓仪们价众优会伞伟传伤伪"
    r"伫体余佣佥侠侣侥侦侧侨侩侪侬俣俦俨俩俪俭债倾偬偻偾偿傥傧储傩兑兰关兴养兽冁内冈册写"
    r"军农冯冲决况冻净凑凛几凤凫凭凯击凿刘则刚创删别刬刭剂剐剑剥剧劝办务劢动励劲劳势勋匀匦"
    r"区医华协单卖卢卤卧卫却厂厅历厉压厌厕厢厣厦厨厩厮县叁参双发变叙叠叶号叹叽吁后吓吕吗听启"
    r"吴呐呒呓呕呖呗员呙呛呜咏咙咛咝咤响哑哒哓哔哕哗哙哜哝哟唛唠唤啧啬啭啮啰啴啸喷喽喾嗫嗳"
    r"嘘嘤嘱噜嚣团园囱围囵国图圆圣场坏块坚坛坝坞坟坠垄垅垆垒垦垩垫垭垯垱垲垴埘埙埚埯堑堕墙"
    r"壮声壳壶处备复够头夹夺奁奂奋奖奥妆妇妈妩妪妫姗姜娄娅娆娇娈娱娲娴婳婴婵婶媪嫒嫔嫱嬷孙"
    r"学孪宁宝实宠审宪宫宽宾寝对寻导寿将尔尘尝尧尴尸尽层屃屉届属屡屦屿岁岂岖岗岘岙岚岛岭岳"
    r"岽岿峃峄峡峤峥峦崂崃崭嵘嵚嵛嵝巅巩巯币帅师帐带帧帮帱帻帼幂庄庆庐庑库应庙庞废庼廪开异"
    r"弃张弥弪弯弹强归当录径徕御忆忏忧忾怀态怂怃怄怅怆怜总怼怿恋恒恳恶恸恹恺恻恼恽悦悫悬悭"
    r"悯惊惧惨惩惫惬惭惮惯愤愦愿慑懑懒懔戆戋戏戗战戬户扎扑执扩扪扫扬扰抚抛抟抠抡抢护报担拟"
    r"拢拣拥拦拧拨择挂挚挛挜挝挞挟挠挡挢挣挤挥挦捞损捡换捣据捻掳掴掷掸掺掼揽揿搀搁搂搅携摄"
    r"摅摆摇摈摊撄撑撵撷撸撺擞攒敌敛数斋斓斗斩断无旧时旷旸昙昼显晋晒晓晔晕晖暂暧术机杀杂权"
    r"条来杨极构枞枢枣枥枧枨枪枫枭柜柠柽栀栅标栈栉栊栋栌栎栏树栖样栾桊桠桡桢档桤桥桦桧桨桩"
    r"梦梼梾检棂椁椟椠椭楼榄榇榈榉槚槛槟槠横樯樱橥橱橹橼檩欢欤欧欲歼殁殇残殒殓殚殡殴毁"
    r"毕毙毡毵氇气氢氩氲汇汉污汤汹沓沟没沣沤沥沦沧沪泞泪泶泷泸泺泻泼泽洁洒洼浃浅浆浇浈浊"
    r"测浍济浏浐浑浒浓浔涛涝涞涟涠涡涣涤润涧涨涩渊渌渍渎渐渑渔渖渗温游湾湿溃溅溆溇滗滚滞"
    r"滟滠满滢滤滥滦滨滩滪漤潆潇潋潍潜潴澜濑濒灏灭灯灵灾灿炀炉炖炜炝点炼炽烁烂烃烈烊烛烟烦"
    r"烧烨烩烫烬热焕焖焘煅煳熘爱爷牍牦牵牺犊状犷犸犹狈狝狞独狭狮狯狰狱狲猃猎猕猡猪猫献獭"
    r"玑玛玮环现玱玺珐珑珰琎琏琐琼瑶瑷璎瓒瓯电画畅畴疖疗疟疠疡疬疮疯疱疴痈痉痒痖痨痪痫瘅瘆"
    r"瘗瘪瘫瘾瘿癞癣癫皑皱皲盏盐监盖盗盘眍眦睁睐睑瞒瞩矫矶矾矿砀码砖砗砚砜砺砻砾础硁硕硖硗"
    r"硙硚确硷碍碛碜碱碹磙礼祃祎祢祯祷祸禀禄禅离秃秆种积称秽秾稆税稣稳穑穷窃窍窑窜窝窥窦窭"
    r"竖竞笃笋笔笕笺笼笾筑筚筛筜筝筹签简箓箦箧箨箩箪箫篑篓篮篱簖籁籴类籼粜粝粤粪粮糁糇紧絷"
    r"纟纠红纣纤纥约级纨纩纪纫纬纭纯纰纱纲纳纵纶纷纸纹纺纽纾线绀绁绂练组绅细织终绉绊绋绌绍"
    r"绎经绑绒结绕绘给绚绛络绝绞统绠绡绢绣绥绦继绩绪绫续绮绯绰绱绲绳维绵绶绷绸绹绺绻综绽"
    r"绾绿缀缁缂缃缄缅缆缇缈缉缋缌缍缎缏缑缒缓缔缕编缗缘缙缚缛缜缝缟缠缡缢缣缤缥缦缧缨缩"
    r"缪缫缬缭缮缯缰缱缲缳缴罂网罗罚罢罴羁羟羡翘耢耧耸耻聂职聍联聩聪肃肠肤肮肴肾肿胀胁胆"
    r"胜胡胧胨胪胫胶脉脍脏脐脑脓脔脚脱脶脸腊腌腘腭腾膑臜舆舣舰舱舻艰艳艺节芈芗芜芦苁苇苈"
    r"苋苌苍苎苏苧苹茎茏茑茔茕茧荆荐荙荚荛荜荞荟荠荡荣荤荥荦荧荨荩荪荫荬荭药莅莜莱莲莳莴"
    r"莶获莸莹莺莼萚萝萤营萦萧萨葱蒇蒉蒋蒌蓝蓟蓠蓣蓥蓦蔷蔹蔺蔼蕰蕲蕴薮藓虏虑虚虫虬虮虽虾"
    r"虿蚀蚁蚂蚕蚬蛊蛎蛏蛮蛰蛱蛲蛳蛴蜕蜗蜡蝇蝈蝉蝎蝼蝾螀螨蟏衅衔补表衬衮袄袅袆袜袭装裆裈"
    r"裢裤裣褛褴见观觃规觅视觇览觉觊觋觌觎觏觐觑觞触觯訚詟誉誊讠计订讣认讥讦讧讨让讪讫训"
    r"议讯记讲讳讴讵讶讷许讹论讼讽设访诀证诂诃评诅识诈诉诊诋诌词诎诏诐译诒诓诔试诖诗诘诙诚"
    r"诛诜话诞诟诠诡询诣诤该详诧诨诩诫诬语诮误诰诱诲诳说诵诶请诸诹诺读诼诽课诿谀谁谂调谄谅"
    r"谆谇谈谊谋谌谍谎谏谐谑谒谓谔谕谖谗谘谙谚谛谜谝谟谠谡谢谣谤谥谦谧谨谩谪谫谬谭谮谯谰谱"
    r"谲谳谴谵谷豮贝贞负贡财责贤败账货质贩贪贫贬购贮贯贰贱贲贳贴贵贶贷贸费贺贻贼贽贾贿赀赁"
    r"赂赃资赅赆赇赈赉赊赋赌赍赎赏赐赑赒赓赔赕赖赗赘赚赛赜赝赞赠赡赢赣赵赶趋趱跃跄跞践跶跷"
    r"跸跹跻踊踌踪踬踯蹑蹒蹰蹿躏躜躯车轧轨轩轪轫转轭轮软轰轱轲轳轴轵轶轷轸轹轺轻轼载轾轿"
    r"辀辁辂较辄辅辆辇辈辉辊辋辌辍辎辏辐辑输辔辕辖辗辘辙辚辞辩辫边辽达迁过迈运还这进远违连"
    r"迟迩迳迹适选逊递逦逻遗遥邓邝邬邮邹邺邻郁郏郐郑郓郦郧郸酂酝酦酱酽酾酿释鉴銮錾钅钆钇"
    r"针钉钊钋钌钍钎钏钐钓钔钕钗钙钚钛钜钝钞钟钠钡钢钣钤钥钦钧钨钩钪钫钬钭钮钯钰钱钲钳钴"
    r"钵钶钷钸钹钺钻钼钽钾钿铀铁铂铃铄铅铆铈铉铊铋铌铍铎铐铑铒铕铗铘铙铚铛铜铝铞铟铠铡铢"
    r"铣铤铥铦铧铨铩铪铫铬铭铮铯铰铱铲铳铴铵银铷铸铹铺铻铼铽链铿销锁锂锃锄锅锆锇锈锉锋锌"
    r"锍锎锏锐锑锒锓锔锕锖锗错锚锛锜锝锞锟锠锡锢锣锤锥锦锧锨锩锪锫锬锭键锯锰锱锲锳锴锵锶"
    r"锷锸锹锺锻锼锽锾锿镀镁镂镄镅镆镇镈镉镊镋镌镍镎镏镐镑镒镓镔镕镖镗镘镙镚镜镝镞镟镠镡"
    r"镢镣镤镥镦镧镨镩镪镫镬镭镯镰镱镲镳门闩闪闫闭问闯闰闲间闵闶闷闸闹闺闻闼闽闾阀阁阂阃"
    r"阄阅阆阇阈阉阊阋阌阍阎阏阐阑阒阔阕阖阗阘阙阚队阳阴阵阶际陆陇陈陉陕陧陨险随隐隶隽难雏"
    r"雠雳雾霁霉霭靓静靥鞑鞒鞯鞴韦韧韩韪韫韬韵页顶顷顸项顺须顼顽顾顿颀颁颂预颅领颇颈颉"
    r"颊颌颍颎颏颐频颓颖颗题颙颚颛颜额颞颟颠颡颢颤颥颦颧风飏飐飑飒飓飕飘飙飚飞飨餍饥饧饨"
    r"饩饪饫饬饭饮饯饰饱饲饴饵饶饷饸饹饺饻饼饽饿馀馁馃馄馅馆馇馈馊馋馍馎馏馐馑馒馓馔馕马"
    r"驭驮驯驰驱驳驴驶驹驻驼驽驾驿骀骁骂骄骅骆骇骈骊骋验骍骎骏骐骑骒骓骖骗骘骚骛骜骝骞骟"
    r"骠骡骢骣骤骥骧髅髋髌鬓魇魉鱼鱿鲁鲂鲅鲆鲇鲈鲋鲍鲎鲐鲑鲒鲔鲕鲚鲛鲜鲞鲟鲠鲡鲢鲣鲤鲥鲦"
    r"鲧鲨鲩鲫鲭鲮鲰鲱鲲鲳鲴鲵鲶鲷鲸鲹鲺鲻鲼鲽鳄鳅鳆鳇鳌鳍鳎鳏鳐鳓鳔鳕鳖鳗鳘鳙鳜鳝鳞鳟"
    r"鳢鸟鸠鸡鸢鸣鸥鸦鸨鸩鸪鸫鸬鸭鸯鸱鸲鸳鸵鸶鸷鸸鸹鸺鸻鸽鸾鸿鹁鹂鹃鹄鹅鹆鹇鹈鹉鹊鹋鹌"
    r"鹎鹏鹐鹑鹒鹓鹔鹕鹖鹗鹘鹚鹛鹜鹞鹟鹠鹡鹢鹣鹤鹦鹧鹨鹩鹪鹫鹬鹭鹰鹱鹲鹳鹴鹾麦麸黄黉黡黩"
    r"黪黾鼋鼍鼹齄齐齑齿龀龁龂龃龄龅龆龇龈龉龊龋龌龙龚龛龟]")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def iter_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, list):
        for item in value:
            yield from iter_strings(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from iter_strings(item)


def main() -> int:
    errors: list[str] = []
    zh_pack = load_json(LOCALE_DIR / "zh-CN.json")
    cards_config = load_json(CARDS_JSON)

    for locale in NEW_LOCALES:
        if locale not in card_data.SUPPORTED_LOCALES:
            errors.append(f"{locale} missing from SUPPORTED_LOCALES")
        if locale not in cards_config.get("locales", []):
            errors.append(f"{locale} missing from cards.json locales")

    for locale, filename in NEW_LOCALES.items():
        path = LOCALE_DIR / filename
        if not path.exists():
            errors.append(f"missing locale file {filename}")
            continue
        pack = load_json(path)
        if pack.get("locale") != locale:
            errors.append(f"{filename} has wrong locale {pack.get('locale')!r}")
        missing_phrases = set(zh_pack["phrases"]) - set(pack.get("phrases", {}))
        if missing_phrases:
            errors.append(f"{locale} missing phrases: {sorted(missing_phrases)[:5]}")
        for mode in ("rogue", "ultimate"):
            expected_ids = set(cards_config["cards"][mode])
            actual_ids = set(pack.get("cards", {}).get(mode, {}))
            if actual_ids != expected_ids:
                errors.append(f"{locale} {mode} card ids mismatch")
            for card_id, card in cards_config["cards"][mode].items():
                for field in ("name", "desc"):
                    if not card.get(field, {}).get(locale):
                        errors.append(f"{mode}.{card_id}.{field} missing {locale}")
                    if not pack.get("cards", {}).get(mode, {}).get(card_id, {}).get(field):
                        errors.append(f"{filename} {mode}.{card_id}.{field} missing")
        for key, spec in cards_config["tuning"].items():
            if not spec.get("label", {}).get(locale):
                errors.append(f"tuning {key} missing {locale} label")

    for locale in FR_DE_LOCALES:
        filename = NEW_LOCALES[locale]
        pack = load_json(LOCALE_DIR / filename)
        for text in iter_strings(pack):
            if CJK_RE.search(text):
                errors.append(f"{locale} locale text contains CJK residue: {text}")
                break
        for mode in ("rogue", "ultimate"):
            for card_id, card in cards_config["cards"][mode].items():
                for field in ("name", "desc"):
                    text = card[field][locale]
                    if CJK_RE.search(text):
                        errors.append(f"{mode}.{card_id}.{field} {locale} contains CJK residue")
        for key, spec in cards_config["tuning"].items():
            text = spec["label"][locale]
            if CJK_RE.search(text):
                errors.append(f"tuning {key} {locale} contains CJK residue")

    zht_pack = load_json(LOCALE_DIR / "zh-TW.json")
    zht_values = list(iter_strings(zht_pack))
    for mode in ("rogue", "ultimate"):
        for card in cards_config["cards"][mode].values():
            zht_values.extend([card["name"]["zh-TW"], card["desc"]["zh-TW"]])
    for spec in cards_config["tuning"].values():
        zht_values.append(spec["label"]["zh-TW"])
    zht_residue_samples = []
    for text in zht_values:
        if ZHT_SIMPLIFIED_RESIDUE_RE.search(text):
            zht_residue_samples.append(text)
            if len(zht_residue_samples) >= 5:
                break
    if zht_residue_samples:
        errors.append(f"zh-TW text contains simplified residue: {zht_residue_samples}")

    marker_expectations = {
        ROOT / "static" / "js" / "i18n.js": ("zh-TW", "fr-FR", "de-DE", "zht", "fr", "de"),
        ROOT / "static" / "js" / "localization_ui.js": ("zh-TW", "zht", "fr", "de"),
        ROOT / "static" / "js" / "card_catalog.js": ("zh-TW", "fr-FR", "de-DE", "zht", "fr", "de"),
        ROOT / "static" / "card_editor.html": ("zh-TW", "fr-FR", "de-DE", "zht", "fr", "de"),
    }
    for file_path, markers in marker_expectations.items():
        text = file_path.read_text(encoding="utf-8")
        for marker in markers:
            if marker not in text:
                errors.append(f"{file_path.relative_to(ROOT)} missing marker {marker}")

    if errors:
        raise AssertionError("\n".join(errors))
    print("locale pack completeness smoke test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
