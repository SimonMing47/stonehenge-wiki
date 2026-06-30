from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from .models import DocumentRecord

EMU = 914400
SLIDE_W = 13_333_333
SLIDE_H = 7_500_000


@dataclass(frozen=True)
class SlideSpec:
    title: str
    bullets: list[str]
    kicker: str = ""


def create_presentation(
    wiki_root: Path,
    topic: str,
    answer_datas: list[str],
    records: list[DocumentRecord],
    slide_count: int = 6,
) -> tuple[str, list[SlideSpec]]:
    slides = build_slide_specs(topic, answer_datas, records, slide_count)
    output_dir = wiki_root / "output" / "presentations"
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{slugify(topic or 'stonehenge-wiki-brief')}.pptx"
    write_pptx(target, slides)
    return target.relative_to(wiki_root).as_posix(), slides


def build_slide_specs(
    topic: str,
    answer_datas: list[str],
    records: list[DocumentRecord],
    slide_count: int,
) -> list[SlideSpec]:
    slide_count = max(3, min(int(slide_count or 6), 10))
    title = topic.strip() or "Stonehenge Wiki Brief"
    answer_text = "\n".join(answer_datas)
    points = extract_points(answer_text)
    sources = [record.rel_path for record in records[:8]]
    comments = []
    for record in records:
        for comment in record.comments[:3]:
            comments.append(comment.summary())
        if len(comments) >= 6:
            break

    slides: list[SlideSpec] = [
        SlideSpec(title=title[:72], kicker="Stonehenge Wiki", bullets=["自动从知识库检索、汇总并生成", f"引用来源 {len(sources)} 个"]),
        SlideSpec(title="核心回答", kicker="Answer", bullets=points[:5] or ["暂无足够材料生成摘要"]),
        SlideSpec(title="来源依据", kicker="Raw", bullets=sources[:6] or ["暂无匹配来源"]),
    ]
    if comments:
        slides.append(SlideSpec(title="待办与批注", kicker="TODO", bullets=comments[:5]))
    remaining_points = points[5:10]
    if remaining_points:
        slides.append(SlideSpec(title="补充要点", kicker="Details", bullets=remaining_points[:5]))
    slides.append(
        SlideSpec(
            title="建议动作",
            kicker="Next",
            bullets=[
                "确认引用来源是否覆盖本次汇报范围",
                "补齐缺失数据或待办责任人",
                "生成后可继续在 PowerPoint 中调整版式和图表",
            ],
        )
    )
    appendix_idx = 1
    while len(slides) < slide_count:
        source_slice = sources[(appendix_idx - 1) * 5 : appendix_idx * 5]
        bullets = source_slice or ["暂无更多来源"]
        slides.append(SlideSpec(title=f"来源附录 {appendix_idx}", kicker="Appendix", bullets=bullets))
        appendix_idx += 1
    return slides[:slide_count]


def extract_points(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        line = re.sub(r"^[\s>*#`-]+", "", raw).strip(" `")
        if not line or line.lower().startswith(("llm:", "sources:")):
            continue
        if line.startswith("引用文件"):
            continue
        if len(line) > 140:
            parts = re.split(r"[。；;]", line)
            lines.extend(part.strip() for part in parts if part.strip())
        else:
            lines.append(line)
    seen: set[str] = set()
    result: list[str] = []
    for line in lines:
        cleaned = re.sub(r"\s+", " ", line)
        if len(cleaned) < 3 or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned[:160])
    return result


def write_pptx(path: Path, slides: list[SlideSpec]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types(len(slides)))
        zf.writestr("_rels/.rels", root_rels())
        zf.writestr("docProps/app.xml", app_props(len(slides)))
        zf.writestr("docProps/core.xml", core_props())
        zf.writestr("ppt/presentation.xml", presentation_xml(len(slides)))
        zf.writestr("ppt/_rels/presentation.xml.rels", presentation_rels(len(slides)))
        zf.writestr("ppt/slideMasters/slideMaster1.xml", slide_master_xml())
        zf.writestr("ppt/slideMasters/_rels/slideMaster1.xml.rels", slide_master_rels())
        zf.writestr("ppt/slideLayouts/slideLayout1.xml", slide_layout_xml())
        zf.writestr("ppt/slideLayouts/_rels/slideLayout1.xml.rels", slide_layout_rels())
        zf.writestr("ppt/theme/theme1.xml", theme_xml())
        for idx, slide in enumerate(slides, start=1):
            zf.writestr(f"ppt/slides/slide{idx}.xml", slide_xml(slide, idx))
            zf.writestr(f"ppt/slides/_rels/slide{idx}.xml.rels", slide_rels())


def content_types(slide_count: int) -> str:
    slide_overrides = "\n".join(
        f'<Override PartName="/ppt/slides/slide{i}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for i in range(1, slide_count + 1)
    )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>
  <Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
  <Override PartName="/ppt/presentation.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>
  <Override PartName="/ppt/slideMasters/slideMaster1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>
  <Override PartName="/ppt/slideLayouts/slideLayout1.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>
  <Override PartName="/ppt/theme/theme1.xml" ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>
  {slide_overrides}
</Types>'''


def root_rels() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="ppt/presentation.xml"/>
  <Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
  <Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>
</Relationships>'''


def presentation_xml(slide_count: int) -> str:
    slide_ids = "\n".join(f'<p:sldId id="{255 + i}" r:id="rId{i + 1}"/>' for i in range(1, slide_count + 1))
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:presentation xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>
  <p:sldIdLst>{slide_ids}</p:sldIdLst>
  <p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}" type="wide"/>
  <p:notesSz cx="6858000" cy="9144000"/>
  <p:defaultTextStyle/>
</p:presentation>'''


def presentation_rels(slide_count: int) -> str:
    rels = ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="slideMasters/slideMaster1.xml"/>']
    rels.extend(
        f'<Relationship Id="rId{i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide{i}.xml"/>'
        for i in range(1, slide_count + 1)
    )
    return rels_xml(rels)


def slide_master_xml() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldMaster xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>{group_shape()}</p:spTree></p:cSld>
  <p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" folHlink="folHlink"/>
  <p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>
  <p:txStyles><p:titleStyle/><p:bodyStyle/><p:otherStyle/></p:txStyles>
</p:sldMaster>'''


def slide_master_rels() -> str:
    return rels_xml(
        [
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>',
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/theme" Target="../theme/theme1.xml"/>',
        ]
    )


def slide_layout_xml() -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sldLayout xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" type="blank" preserve="1">
  <p:cSld name="Blank"><p:spTree>{group_shape()}</p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sldLayout>'''


def slide_layout_rels() -> str:
    return rels_xml(
        ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideMaster" Target="../slideMasters/slideMaster1.xml"/>']
    )


def slide_rels() -> str:
    return rels_xml(
        ['<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>']
    )


def slide_xml(slide: SlideSpec, idx: int) -> str:
    bullets = "".join(bullet_paragraph(text) for text in slide.bullets[:7])
    kicker = text_shape(2, "kicker", slide.kicker.upper(), 760000, 420000, 5_500_000, 320000, 1200, "64707D", bold=False)
    title = text_shape(3, "title", slide.title, 760000, 860000, 10_900_000, 1_280_000, 3000, "15191F", bold=True)
    body = text_box(4, "body", bullets, 820000, 2_260_000, 11_400_000, 3_900_000)
    footer = text_shape(5, "footer", f"Stonehenge Wiki · {idx}", 760000, 6_820_000, 3_000_000, 280000, 900, "64707D")
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<p:sld xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">
  <p:cSld><p:spTree>{group_shape()}{background_shape()}{kicker}{title}{body}{footer}</p:spTree></p:cSld>
  <p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>
</p:sld>'''


def group_shape() -> str:
    return '''<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/><a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'''


def background_shape() -> str:
    return '''<p:sp><p:nvSpPr><p:cNvPr id="10" name="background"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="13333333" cy="7500000"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:solidFill><a:srgbClr val="F8F7F2"/></a:solidFill><a:ln><a:noFill/></a:ln></p:spPr></p:sp>'''


def text_shape(
    shape_id: int,
    name: str,
    text: str,
    x: int,
    y: int,
    cx: int,
    cy: int,
    size: int,
    color: str,
    bold: bool = False,
) -> str:
    bold_attr = ' b="1"' if bold else ""
    rpr = f'<a:rPr lang="zh-CN" sz="{size}"{bold_attr}><a:solidFill><a:srgbClr val="{color}"/></a:solidFill><a:latin typeface="Arial"/><a:ea typeface="PingFang SC"/></a:rPr>'
    paragraph = f"<a:p><a:r>{rpr}<a:t>{xml(text)}</a:t></a:r></a:p>"
    return text_box(shape_id, name, paragraph, x, y, cx, cy)


def text_box(shape_id: int, name: str, paragraphs: str, x: int, y: int, cx: int, cy: int) -> str:
    return f'''<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{xml(name)}"/><p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/><a:ln><a:noFill/></a:ln></p:spPr><p:txBody><a:bodyPr wrap="square"/><a:lstStyle/>{paragraphs}</p:txBody></p:sp>'''


def bullet_paragraph(text: str) -> str:
    return f'''<a:p marL="285750" indent="-171450"><a:buChar char="•"/><a:r><a:rPr lang="zh-CN" sz="1700"><a:solidFill><a:srgbClr val="20242A"/></a:solidFill><a:latin typeface="Arial"/><a:ea typeface="PingFang SC"/></a:rPr><a:t>{xml(text)}</a:t></a:r></a:p>'''


def app_props(slide_count: int) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes"><Application>Stonehenge Wiki</Application><PresentationFormat>On-screen Show (16:9)</PresentationFormat><Slides>{slide_count}</Slides></Properties>'''


def core_props() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" xmlns:dcmitype="http://purl.org/dc/dcmitype/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"><dc:title>Stonehenge Wiki Brief</dc:title><dc:creator>Stonehenge Wiki</dc:creator></cp:coreProperties>'''


def theme_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="Stonehenge Wiki"><a:themeElements><a:clrScheme name="Stonehenge Wiki"><a:dk1><a:srgbClr val="15191F"/></a:dk1><a:lt1><a:srgbClr val="F8F7F2"/></a:lt1><a:dk2><a:srgbClr val="20242A"/></a:dk2><a:lt2><a:srgbClr val="FFFFFF"/></a:lt2><a:accent1><a:srgbClr val="1F6F68"/></a:accent1><a:accent2><a:srgbClr val="64707D"/></a:accent2><a:accent3><a:srgbClr val="D7C7A4"/></a:accent3><a:accent4><a:srgbClr val="475569"/></a:accent4><a:accent5><a:srgbClr val="9A3412"/></a:accent5><a:accent6><a:srgbClr val="155E75"/></a:accent6><a:hlink><a:srgbClr val="1F6F68"/></a:hlink><a:folHlink><a:srgbClr val="64707D"/></a:folHlink></a:clrScheme><a:fontScheme name="Stonehenge Wiki"><a:majorFont><a:latin typeface="Arial"/><a:ea typeface="PingFang SC"/></a:majorFont><a:minorFont><a:latin typeface="Arial"/><a:ea typeface="PingFang SC"/></a:minorFont></a:fontScheme><a:fmtScheme name="Stonehenge Wiki"><a:fillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:fillStyleLst><a:lnStyleLst><a:ln w="6350"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln></a:lnStyleLst><a:effectStyleLst><a:effectStyle><a:effectLst/></a:effectStyle></a:effectStyleLst><a:bgFillStyleLst><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:bgFillStyleLst></a:fmtScheme></a:themeElements></a:theme>'''


def rels_xml(rels: list[str]) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{"".join(rels)}</Relationships>'''


def slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff._-]+", "-", text.strip()).strip("-")
    return (slug or "stonehenge-wiki-brief")[:80]


def xml(text: str) -> str:
    return escape(str(text), {'"': "&quot;"})
