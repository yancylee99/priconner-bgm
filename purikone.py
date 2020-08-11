import os, shutil, hashlib, sqlite3, subprocess, struct


USER_NAME = 'Lee'
DATA_DIR = 'c:/Users/{0}/AppData/LocalLow/Cygames/PrincessConnectReDive'.format(USER_NAME)
CURRENT_DIR = os.path.dirname(os.path.realpath(__file__))
MANIFEST_FILENAME = 'manifest.db'
ASSET_DIR = 'b'
OUT_DIR = 'out'
TEMP_DIR = 'temp'

SHOULD_CLEAN = True

VGMSTREAM_PATH = 'vendor/vgmstream/test.exe'
HCA_KEY = 0x30D9E8
IS_BATCH = True # Use a single keyfile. Otherwise, use per-file keyfiles. vgmstream will derive the subkey.
SKIP_SUBKEY = True # When IS_BATCH is False, vgmstream will read the subkey. Otherwise, we do.
DEFAULT_LOOPS = 2


def create_or_clean_dir(dirname):
    if os.path.exists(dirname):
        for f in os.listdir(dirname):
            os.remove(os.path.join(dirname, f))
    else:
        os.makedirs(dirname)


def make_keyfile(awb_path = ''):
    subkey = 0
    key_path = os.path.join(TEMP_DIR, '.hcakey')

    if awb_path and not IS_BATCH:
        key_path = awb_path + '.hcakey'

        if not SKIP_SUBKEY:
            f = open(awb_path, 'rb')
            f.seek(14)
            subkey = struct.unpack('<h', f.read(2))[0]
            f.close()

    if IS_BATCH or SKIP_SUBKEY:
        key = struct.pack('>q', HCA_KEY)
    else:    
        key = struct.pack('>qh', HCA_KEY, subkey)

    f = open(key_path, 'wb')
    f.write(key)
    f.close()


def fetch_db_files(db_path):
    db = sqlite3.connect(db_path)
    cursor = db.cursor()
    subpath = ASSET_DIR + '/'
    cursor.execute('SELECT k FROM t WHERE k LIKE "{0}%"'.format(subpath))
    files = [r[0][len(subpath):] for r in cursor.fetchall()]
    db.close()
    
    return files


def copy_db_files(files, src_dir, dst_dir):
    hashes = [hashlib.sha1(f.encode('utf-8')).hexdigest() for f in files]
    for hash, file in zip(hashes, files):
        src = os.path.join(src_dir, hash)
        dst = os.path.join(dst_dir, file)
        shutil.copy(src, dst)


def execute_get_words(*args):
    output = subprocess.check_output(args)
    return [line.split(b' ') for line in output.split(str.encode(os.linesep))]


def process_awb(awb):
    awb_path = os.path.join(TEMP_DIR, awb)

    if not IS_BATCH:
        make_keyfile(awb_path)    

    lines = execute_get_words(VGMSTREAM_PATH, '-m', awb_path)

    stream_count = 1
    for line in lines:
        if len(line) > 2 and line[0].startswith(b'stream') and line[1].startswith(b'count'):
            stream_count = int(line[2])
            break

    out_path = os.path.join(CURRENT_DIR, OUT_DIR)
    for i in range(1, stream_count + 1):
        decompress_awb(awb_path, out_path, i)

    if SHOULD_CLEAN:
        awb_root = awb_path[:-4]
        os.remove(awb_root + '.awb')
        os.remove(awb_root + '.acb')
        if not IS_BATCH:
            os.remove(awb_root + '.awb.hcakey')


def decompress_awb(awb_path, out_dir, index = 1):
    lines = execute_get_words(VGMSTREAM_PATH, '-s', str(index), '-m', awb_path)

    names = []
    for line in lines:
        if len(line) > 2 and line[0].startswith(b'stream') and line[1].startswith(b'name'):
            names = b' '.join(line[2:]).split(b'; ')
            break
    
    out_name = names[0] + b'.wav'

    loop_arg = '-F'
    loops = DEFAULT_LOOPS
    if loops > 0:
        loop_arg = '-l {0}'.format(loops)

    out_path = os.path.join(out_dir, str(out_name)[2:-1])
    subprocess.call([VGMSTREAM_PATH, loop_arg, '-s', str(index), '-o', out_path, awb_path])
    print('')


if __name__ == "__main__":
    create_or_clean_dir(TEMP_DIR)

    print ("-- Reading database...")
    db_path = os.path.join(DATA_DIR, MANIFEST_FILENAME)
    files = fetch_db_files(db_path)

    print ("-- Copying {0} files...".format(len(files)))
    asset_path = os.path.join(DATA_DIR, ASSET_DIR)
    copy_db_files(files, asset_path, TEMP_DIR)

    if IS_BATCH:
        make_keyfile()

    create_or_clean_dir(OUT_DIR)
    
    awb_files = [f for f in files if f.endswith('.awb')]

    for awb_index, awb in enumerate(awb_files, start=1):
        print('-- Processing {0} ({1} of {2})...\n'.format(awb, awb_index, len(awb_files)))
        process_awb(awb)

    if SHOULD_CLEAN:
        shutil.rmtree(TEMP_DIR, ignore_errors=True)

    print('Done.')
