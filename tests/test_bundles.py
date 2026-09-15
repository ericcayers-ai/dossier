from dossier.bundles import *
def test_bundle_names():
 r=Rules(['job-posting-','keywords-'],['_CoverLetter'],['-page-\\d+','_Sep2026'])
 assert stem_key('job-posting-Northbridge_Sep2026.md',r)==stem_key('keywords-Northbridge_Sep2026_CoverLetter.docx',r)
def test_roles():
 r=Rules([],[],[]); assert classify_role('job-posting-x.md',r)=='source'; assert classify_role('x.docx',r)=='artifact'
