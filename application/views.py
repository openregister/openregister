import json

from flask import (
    render_template,
    request,
    make_response,
    Markup,
    abort,
    current_app,
    flash,
    redirect,
    url_for
)

from application import app, db
from .registry import registers, Register
from entry.representations import representations as _representations
from .utils import log_traceback


def link(register, field, value):
    return ('<a href="http://%s.%s/%s/%s">%s</a>'
            % (register, app.config['REGISTER_DOMAIN'], field, value, value))


# TBD: should be a register of filters for a Field/Datatype ..
@app.template_filter('datatype')
def datatype_filter(value, fieldname):

    # datatypes
    if fieldname == "sameAs":
        return Markup('<a href="%s">%s</a>' % (value, value))
    if fieldname == "hash":
        return Markup('<a href="/hash/%s">%s</a>' % (value, value))
    if fieldname == "name":
        return Markup('<a href="/name/%s">%s</a>' % (value, value))

    # link by hash
    if fieldname == "address":
        return Markup(link("address", "hash", value))

    # link by name
    if fieldname == "addressCountry":
        return Markup(link("country", "addressCountry", value))
    if fieldname == "register":
        return Markup(link("register", "register", value))
    if fieldname == "field":
        return Markup(link("field", "field", value))
    if fieldname == "fields":
        return Markup([link('field', 'field', v) for v in value])

    return value


@app.template_filter('thousands_comma')
def thousands_comma_filter(value):
    if value:
        return "{:,d}".format(value)
    return value


# TBD: push this into entry.representations ..
representations = {}
for representation in _representations:
    module = __import__('entry.representations.' + representation,
                        globals(),
                        locals(),
                        ['content_type'])
    if module.content_type:
        representations[representation] = module


def subdomain(request):
    subdomain = request.headers['Host'].split('.')[0]
    if '-' in subdomain:
        return subdomain.split('-')[0]
    else:
        return subdomain


def represent_entry(entry, suffix):
    text = getattr(entry, suffix)
    return create_response(text, suffix)


def json_representation(entry):
    data = {"hash": entry.hash, "entry": entry.primitive}
    out = json.dumps(
        data,
        sort_keys=True,
        ensure_ascii=False)
    return create_response(out, 'json')


def represent_entries(entries, suffix):

    # temp hack to wrap entry with hash as metadata
    if suffix == 'json':
        data = []
        for entry in entries:
            data.append({"hash": entry.hash, "entry": entry.primitive})
        text = json.dumps(
            data,
            sort_keys=True,
            ensure_ascii=False)
    else:
        response_data = [getattr(entry, suffix) for entry in entries]
        text = '[' + ",".join(response_data) + ']'
    return create_response(text, suffix)


def create_response(text, suffix):
    resp = make_response(text, 200)
    resp.headers['Content-Type'] = representations[suffix].content_type
    return resp


@app.route("/hash/<hash>")
def entry_by_hash(hash):
    return entry_by_hash_suffix(hash, "html")


@app.route("/hash/<hash>.<suffix>")
def entry_by_hash_suffix(hash, suffix="html"):
    register_name = subdomain(request)
    register = find_or_initalise_register(register_name)
    entry = register._store.get(hash)
    return render_entry(entry, "entry.html", register, suffix)


def render_entry(entry, template, register, suffix):
    if entry:
        if suffix == "html":
            return render_template(template,
                                   register=register.primitive,
                                   representations=representations,
                                   hash=entry.hash,
                                   entry=entry.primitive)

    if suffix in representations:
        # temp hack to wrap entry with hash as metadata
        if suffix == "json":
            return json_representation(entry)
        else:
            return represent_entry(entry, suffix)
    else:
        abort(404)


@app.route("/")
def entries():
    return find_entries(query={},
                        page=int(request.args.get('page', 1)))


@app.route("/search")
def search():
    return search_with_suffix('html')


@app.route("/search.<suffix>")
def search_with_suffix(suffix):

    field = request.args.get('field')
    value = request.args.get('value')

    if field is None or value is None:
        query = {}
    else:
        query = {field: {'$regex': value, "$options": "-i"}}

    return find_entries(query, suffix=suffix)


# TODO - protect urls like this
@app.route("/load-data")
def load_data():
    '''
        This loads data for a register repository
        e.g. https://github.com/openregister/registername.register.

        It will then load the data contained in the repository and
        load it into the register. Currently that means loading the data
        into the mongodb for the register.
    '''
    register_name = subdomain(request)
    register = registers.get(register_name)
    try:
        if not register:
            register = Register(register_name.capitalize(),
                                current_app.config['MONGO_URI'])
            registers[register_name] = register
        zip_url = '%s/%s.register/archive/master.zip' % \
                  (current_app.config['GITHUB_ORG'], register_name)
        register.load_remote(zip_url)
        flash('Loaded data into register')
    except Exception as ex:
        log_traceback(current_app.logger, ex)
        flash('Problem loading data into register', 'error')

    return redirect(url_for('entries', _external=True))


@app.route("/<key>/<value>")
def find_latest_entry_by_kv(key, value):
    return find_latest_entry(query={key: value})


def find_latest_entry(query={}):
    register_name = subdomain(request)
    register = find_or_initalise_register(register_name)
    meta, entries = register._store.find(query)
    entry = entries[0]  # egregious hack to find latest ..)
    return entry_by_hash_suffix(entry.hash, "html")


def find_entries(query={}, suffix="html", page=None):
    register_name = subdomain(request)
    register = find_or_initalise_register(register_name)

    if not page:
        page = 1
    meta, entries = register._store.find(query, page)

    entries_list = [[entry.hash, entry.primitive] for entry in entries]
    entry_keys = []
    if entries_list:
        entry_keys = [field for field in entries_list[0][1]]
        # TBD: order by field names in the register
        entry_keys.sort()
        if "name" in entry_keys:
            entry_keys.remove("name")
            entry_keys = ["name"] + entry_keys
    if suffix == "html":
        return render_template("entries.html",
                               register=register.primitive,
                               representations=representations,
                               meta=meta,
                               entries_list=entries_list,
                               entry_keys=entry_keys)

    if suffix in representations:
        return represent_entries(entries, suffix)
    else:
        return abort(404)


def find_or_initalise_register(register_name):
    if not registers.get(register_name):
        collections = db.collection_names()
        if register_name not in collections:
            return abort(404)
        registers[register_name] = Register(register_name,
                                            current_app.config['MONGO_URI'])
    return registers.get(register_name)
