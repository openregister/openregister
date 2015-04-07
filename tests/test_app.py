import application
import json

app = application.app.test_client()
db = application.db
registry_url = 'http://openregister.org/'
field_url = 'http://testing.openregister.org/'


def test_get_unknown_domain_404():
    response = app.get('/', base_url='http://no-such-domain.example.org')
    assert response.status_code == 404


def test_get_entries():
    collections = db.collection_names()
    if 'testing' not in collections:
        db.create_collection('testing')
    response = app.get('/', base_url=field_url)
    assert response.status_code == 200


def test_get_entry_404():
    hash = "aaaaaaaaa"
    response = app.get('/hash/%s' % hash, base_url=field_url)
    assert response.status_code == 404


def test_search():
    collections = db.collection_names()
    if 'testing' not in collections:
        db.create_collection('testing')
    collection = db['testing']
    collection.remove()
    collection.insert({"id": 123, "someField": "thevalue"})
    collection.insert({"id": 678, "someField": "thevalue"})
    collection.insert({"id": 234, "someField": "another value"})

    response = app.get('/search.json?field=someField&value=thevalue',
                       base_url=field_url)
    assert response.status_code == 200
    data = json.loads(response.data.decode('utf-8'))
    assert len(data) == 2
    assert data[0]['hash']  # just assert there is a hash for now
    assert data[0]['entry'] == {'id': 123, 'someField': 'thevalue'}
    assert data[1]['hash']
    assert data[1]['entry'] == {'id': 678, 'someField': 'thevalue'}


def test_search_allows_partial_match():
    collections = db.collection_names()
    if 'testing' not in collections:
        db.create_collection('testing')
    collection = db['testing']
    collection.remove()
    collection.insert({"id": 123, "field": "value"})
    search_url = '/search.json?field=field&value=val'

    response = app.get(search_url, base_url=field_url)

    assert response.status_code == 200
    data = json.loads(response.data.decode('utf-8'))
    assert len(data) == 1
    assert data[0]['hash']  # just assert there is a hash for now
    assert data[0]["entry"] == {'id': 123, 'field': 'value'}


def test_search_allows_case_insensitive_match():
    collections = db.collection_names()
    if 'testing' not in collections:
        db.create_collection('testing')
    collection = db['testing']
    collection.remove()
    collection.insert({"id": 123, "field": "VALUE"})
    search_url = '/search.json?field=field&value=value'

    response = app.get(search_url, base_url=field_url)

    assert response.status_code == 200
    data = json.loads(response.data.decode('utf-8'))
    assert len(data) == 1
    assert data[0]['hash']  # just assert there is a hash for now
    assert data[0]["entry"] == {'id': 123, 'field': 'VALUE'}
