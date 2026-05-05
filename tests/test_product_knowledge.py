import pytest
from shopee_agent.app.product_knowledge_agent import ProductKnowledgeAgent
from shopee_agent.contracts.knowledge import FAQEntry, ProductFact
from shopee_agent.persistence.repositories import ProductKnowledgeRepository


def test_pk_agent_upsert_from_api(db_session):
    repo = ProductKnowledgeRepository(db_session)
    agent = ProductKnowledgeAgent(repo)

    item = {"item_id": "1001", "item_name": "Wireless Mouse", "category_id": 123}
    agent.upsert_product_from_api("shop1", item)

    fact = repo.get_pk("shop1", "1001")
    assert fact is not None
    assert fact.name == "Wireless Mouse"
    assert fact.category == "123"


def test_pk_agent_add_faq(db_session):
    repo = ProductKnowledgeRepository(db_session)
    agent = ProductKnowledgeAgent(repo)

    agent.upsert_product_from_api("shop1", {"item_id": "1001", "item_name": "Mouse"})
    agent.add_faq("shop1", "1001", "Is it silent?", "Yes, it is.")

    fact = repo.get_pk("shop1", "1001")
    assert len(fact.faq) == 1
    assert fact.faq[0].question == "Is it silent?"


def test_pk_agent_lookup(db_session):
    repo = ProductKnowledgeRepository(db_session)
    agent = ProductKnowledgeAgent(repo)

    agent.upsert_product_from_api("shop1", {"item_id": "1001", "item_name": "Mechanical Keyboard"})
    
    # Lookup by name fragment
    fact = agent.lookup("shop1", "keyboard")
    assert fact is not None
    assert fact.item_id == "1001"

    # Lookup by ID
    fact_id = agent.lookup("shop1", "1001")
    assert fact_id is not None
    assert fact_id.name == "Mechanical Keyboard"

    # No match
    assert agent.lookup("shop1", "nonexistent") is None
