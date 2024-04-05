import os
import hashlib
import sys
import json
import folder_paths
from server import PromptServer
from .config import RESOURCES_DIR, FOOOCUS_STYLES_DIR, FOOOCUS_STYLES_SAMPLES
from .logic import ConvertAnything
from .libs.model import easyModelManager
from .libs.utils import getMetadata

try:
    import aiohttp
    from aiohttp import web
except ImportError:
    print("Module 'aiohttp' not installed. Please install it via:")
    print("pip install aiohttp")
    sys.exit()

# parse csv
@PromptServer.instance.routes.post("/easyuse/upload/csv")
async def parse_csv(request):
    post = await request.post()
    csv = post.get("csv")
    if csv and csv.file:
        file = csv.file
        text = ''
        for line in file.readlines():
            line = str(line.strip())
            line = line.replace("'", "").replace("b",'')
            text += line + '; \n'
        return web.json_response(text)

#get style list
@PromptServer.instance.routes.get("/easyuse/prompt/styles")
async def getStylesList(request):
    if "name" in request.rel_url.query:
        name = request.rel_url.query["name"]
        if name == 'fooocus_styles':
            file = os.path.join(RESOURCES_DIR, name+'.json')
            cn_file = os.path.join(RESOURCES_DIR, name + '_cn.json')
        else:
            file = os.path.join(FOOOCUS_STYLES_DIR, name+'.json')
            cn_file = os.path.join(FOOOCUS_STYLES_DIR, name + '_cn.json')
        cn_data = None
        if os.path.isfile(cn_file):
            f = open(cn_file, 'r', encoding='utf-8')
            cn_data = json.load(f)
            f.close()
        if os.path.isfile(file):
            f = open(file, 'r', encoding='utf-8')
            data = json.load(f)
            f.close()
            if data:
                ndata = []
                for d in data:
                    nd = {}
                    name = d['name'].replace('-', ' ')
                    words = name.split(' ')
                    key = ' '.join(
                        word.upper() if word.lower() in ['mre', 'sai', '3d'] else word.capitalize() for word in
                        words)
                    img_name = '_'.join(words).lower()
                    if "name_cn" in d:
                        nd['name_cn'] = d['name_cn']
                    elif cn_data:
                        nd['name_cn'] = cn_data[key] if key in cn_data else key
                    nd["name"] = d['name']
                    nd['imgName'] = img_name
                    ndata.append(nd)
                return web.json_response(ndata)
    return web.Response(status=400)

# get style preview image
@PromptServer.instance.routes.get("/easyuse/prompt/styles/image")
async def getStylesImage(request):
    styles_name = request.rel_url.query["styles_name"] if "styles_name" in request.rel_url.query else None
    if "name" in request.rel_url.query:
        name = request.rel_url.query["name"]
        if os.path.exists(os.path.join(FOOOCUS_STYLES_DIR, 'samples')):
            file = os.path.join(FOOOCUS_STYLES_DIR, 'samples', name + '.jpg')
            if os.path.isfile(file):
                return web.FileResponse(file)
            elif styles_name == 'fooocus_styles':
                return web.Response(text=FOOOCUS_STYLES_SAMPLES + name + '.jpg')
        elif styles_name == 'fooocus_styles':
            return web.Response(text=FOOOCUS_STYLES_SAMPLES + name + '.jpg')
    return web.Response(status=400)

# convert type
@PromptServer.instance.routes.post("/easyuse/convert")
async def convertType(request):
    post = await request.post()
    type = post.get('type')
    if type:
        ConvertAnything.RETURN_TYPES = (type.upper(),)
        ConvertAnything.RETURN_NAMES = (type,)
        return web.Response(status=200)
    else:
        return web.Response(status=400)

# get models lists
@PromptServer.instance.routes.get("/easyuse/models/list")
async def getModelsList(request):
    if "type" in request.rel_url.query:
        type = request.rel_url.query["type"]
        if type not in ['checkpoints', 'loras']:
            return web.Response(status=400)
        manager = easyModelManager()
        return web.json_response(manager.get_model_lists(type))
    else:
        return web.Response(status=400)

# get models thumbnails
@PromptServer.instance.routes.get("/easyuse/models/thumbnail")
async def getModelsThumbnail(request):
    checkpoints = folder_paths.get_filename_list("checkpoints_thumb")
    loras = folder_paths.get_filename_list("loras_thumb")
    checkpoints_full = []
    loras_full = []
    for index, i in enumerate(checkpoints):
        full_path = folder_paths.get_full_path('checkpoints_thumb', str(i))
        if full_path:
            checkpoints_full.append(full_path)
    for index, i in enumerate(loras):
        full_path = folder_paths.get_full_path('loras_thumb', str(i))
        if full_path:
            loras_full.append(full_path)
    return web.json_response(checkpoints_full + loras_full)

@PromptServer.instance.routes.get("/easyuse/metadata/{name}")
async def load_metadata(request):
    name = request.match_info["name"]
    pos = name.index("/")
    type = name[0:pos]
    name = name[pos+1:]

    file_path = None
    if type == "embeddings":
        name = name.lower()
        files = folder_paths.get_filename_list(type)
        for f in files:
            lower_f = f.lower()
            if lower_f == name:
                file_path = folder_paths.get_full_path(type, f)
            else:
                n = os.path.splitext(f)[0].lower()
                if n == name:
                    file_path = folder_paths.get_full_path(type, f)

            if file_path is not None:
                break
    else:
        file_path = folder_paths.get_full_path(type, name)
    if not file_path:
        return web.Response(status=404)

    try:
        header = getMetadata(file_path)
        header_json = json.loads(header)
        meta = header_json["__metadata__"] if "__metadata__" in header_json else None
    except:
        meta = None

    if meta is None:
        meta = {}

    file_no_ext = os.path.splitext(file_path)[0]

    info_file = file_no_ext + ".txt"
    if os.path.isfile(info_file):
        with open(info_file, "r") as f:
            meta["easyuse.notes"] = f.read()

    hash_file = file_no_ext + ".sha256"
    if os.path.isfile(hash_file):
        with open(hash_file, "rt") as f:
            meta["easyuse.sha256"] = f.read()
    else:
        with open(file_path, "rb") as f:
            meta["easyuse.sha256"] = hashlib.sha256(f.read()).hexdigest()
        with open(hash_file, "wt") as f:
            f.write(meta["easyuse.sha256"])

    return web.json_response(meta)



NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}