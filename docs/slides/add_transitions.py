"""LT_slides.pptx の全スライドにフェード切り替え効果を追加."""
from pptx import Presentation
from lxml import etree

NS_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
TRANSITION_XML = f"""<p:transition xmlns:p="{NS_P}" spd="med"><p:fade/></p:transition>"""


def add_fade_transitions(path: str) -> None:
    prs = Presentation(path)
    for slide in prs.slides:
        sld = slide.element  # <p:sld>
        # 既存の transition を削除
        for old in sld.findall(f"{{{NS_P}}}transition"):
            sld.remove(old)
        # transition 要素を追加 (順序が厳密に決まっている: timing, transition の前後)
        # transition は cSld の直後、timing の前に置く
        transition = etree.fromstring(TRANSITION_XML)
        # timing 要素があればその前に、なければ末尾に追加
        timing = sld.find(f"{{{NS_P}}}timing")
        if timing is not None:
            timing.addprevious(transition)
        else:
            sld.append(transition)
    prs.save(path)
    print(f"Fade transitions added to {len(prs.slides)} slides.")


if __name__ == "__main__":
    add_fade_transitions("LT_slides.pptx")
