from dossier.bundles import Rules, classify_role, stem_key


def test_bundle_names():
    rules = Rules(['job-posting-', 'keywords-'], ['_CoverLetter'], ['-page-\\d+', '_Sep2026'])
    assert stem_key('job-posting-Northbridge_Sep2026.md', rules) == stem_key(
        'keywords-Northbridge_Sep2026_CoverLetter.docx', rules)


def test_roles():
    rules = Rules([], [], [])
    assert classify_role('job-posting-x.md', rules) == 'source'
    assert classify_role('x.docx', rules) == 'artifact'
