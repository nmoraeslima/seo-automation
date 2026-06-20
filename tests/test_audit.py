from seo_automation.audit import PageData, analyze


def _page(url, **kw):
    base = dict(
        status=200, title="Titulo unico " + url, meta_description="desc " + url,
        h1s=["H1"], images_without_alt=0, has_canonical=True, noindex=False,
        load_ms=500, links=[],
    )
    base.update(kw)
    return PageData(url=url, **base)


def test_detects_missing_title_and_description():
    pages = [_page("https://a.com/", title="", meta_description="")]
    issues = analyze(pages)
    problems = {i.problem for i in issues}
    assert "Title ausente" in problems
    assert "Meta description ausente" in problems


def test_detects_duplicate_titles():
    pages = [
        _page("https://a.com/1", title="Mesmo Titulo"),
        _page("https://a.com/2", title="Mesmo Titulo"),
    ]
    issues = analyze(pages)
    dup = [i for i in issues if i.problem == "Title duplicado"]
    assert len(dup) == 2


def test_detects_broken_status_and_noindex():
    pages = [
        _page("https://a.com/404", status=404),
        _page("https://a.com/hidden", noindex=True),
    ]
    issues = analyze(pages)
    problems = {i.problem for i in issues}
    assert "Status 404" in problems
    assert "Pagina com noindex" in problems


def test_detects_missing_h1_and_images_alt():
    pages = [_page("https://a.com/x", h1s=[], images_without_alt=3)]
    issues = analyze(pages)
    problems = {i.problem for i in issues}
    assert "H1 ausente" in problems
    assert "Imagens sem alt" in problems
