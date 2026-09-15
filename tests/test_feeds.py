from dossier.feeds import *
def test_fixture_adapters():
 assert Greenhouse().parse({'jobs':[{'id':1,'title':'X'}]})[0].title=='X'
def test_prohibited_no_client():
 a=adapter('linkedin')
 try: a.fetch()
 except FeedPolicyError: assert True
 else: assert False
