from flask import (
    render_template,
    request,
    make_response,
    Markup,
    redirect,
    url_for,
    abort,
    flash,
    current_app
)

from application import app, db
from .registry import registers, Register
from thingstance.representations import representations as _representations


# TBD: register url should be constructed from the register object ..
def register_filter(register):
    result = ('<a href="http://%s.register.dev"'
              ' class="register">%s</a>' % (register, register))
    return Markup(result)


# TBD: should be a register of filters for a Field/Datatype ..
@app.template_filter('datatype')
def datatype_filter(value, fieldname):
    if fieldname == "sameAs":
        return Markup('<a href="%s">%s</a>' % (value, value))
    if fieldname == "address":
        return Markup('<a href="http://address.%s/hash/%s">%s</a>'
                      % (app.config['REGISTER_DOMAIN'], value, value))
    if fieldname == "addressCountry":
        return Markup('<a href="http://country.%s/name/%s">%s</a>'
                      % (app.config['REGISTER_DOMAIN'], value, value))
    if fieldname == "register":
        return register_filter(value)
    elif fieldname == "hash":
        return Markup('<a href="/hash/%s">%s</a>' % (value, value))
    return value


# TBD: push this into thingstance.representations ..
representations = {}
for representation in _representations:
    module = __import__('thingstance.representations.' + representation,
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


def represent_thing(thing, suffix):
    text = getattr(thing, suffix)
    resp = make_response(text, 200)
    resp.headers['Content-Type'] = representations[suffix].content_type
    return resp


@app.route("/hash/<hash>")
def thing_by_hash(hash):
    return thing_by_hash_suffix(hash, "html")


@app.route("/hash/<hash>.<suffix>")
def thing_by_hash_suffix(hash, suffix="html"):
    register_name = subdomain(request)
    register = find_or_initalise_register(register_name)
    thing = register._store.get(hash)
    if thing:
        if suffix == "html":
            return render_template("thing.html",
                                   register=register.primitive,
                                   representations=representations,
                                   hash=hash,
                                   thing=thing.primitive)

        if suffix in representations:
                return represent_thing(thing, suffix)
    else:
        abort(404)


@app.route("/")
def things():
    return find_things("Thing", query={}, page=int(request.args.get('page', 1)))


@app.route("/name/<name>")
def find_latest_thing_by_name(name):
    return find_latest_thing(query={"name": name})


def find_latest_thing(query={}, suffix="html"):
    register_name = subdomain(request)
    register = find_or_initalise_register(register_name)
    meta, things = register._store.find(query)
    thing = things[0]  # egregious hack to find latest ..
    return thing_by_hash_suffix(thing.hash, "html")


def find_things(tag, query={}, suffix="html", page=None):
    register_name = subdomain(request)
    register = find_or_initalise_register(register_name)

    if not page:
        page = 1
    meta, things = register._store.find(query, page)

    things_list = [[thing.hash, thing.primitive] for thing in things]
    thing_keys = []
    if things_list:
        thing_keys = [field for field in things_list[0][1]]
        if 'register' in thing_keys:
            thing_keys.remove('register')
        if 'name' in thing_keys:
            thing_keys.remove('name')
        thing_keys.sort()
    if suffix == "html":
        return render_template("things.html",
                               register=register.primitive,
                               representations=representations,
                               meta=meta,
                               things_list=things_list,
                               thing_keys=thing_keys)


def find_or_initalise_register(register_name):
    if not registers.get(register_name):
        collections = db.collection_names()
        if register_name not in collections:
            return abort(404)
        registers[register_name] = Register(register_name, current_app.config['MONGO_URI'])
    return registers.get(register_name)
