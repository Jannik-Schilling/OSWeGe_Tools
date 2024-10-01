import urllib.request

def get_metadata(file_path, lokal=True):
    if lokal:
        with open(file_path, 'r') as f:
            text = f.readlines()
    else:
        response = urllib.request.urlopen(file_path)
        text = response.read().decode('utf-8').split('\n')
    has_repo = False
    has_version = False
    repo_line = ''
    version_line = ''
    for line in text:
        if line.startswith('repository='):
            repo_line = line.split('=')[1].strip()
            has_repo = True
        if line.startswith('version='):
            version_line = line.split('=')[1].strip()
            has_repo = True
        if has_repo and has_version:
            break
    return repo_line, version_line

def compare_versions(vers1, vers2):
    parts1 = list(map(int, vers1.split('.')))
    parts2 = list(map(int, vers2.split('.')))
    length = max(len(parts1), len(parts2))
    for i in range(length):
        part1 = parts1[i] if i < len(parts1) else 0
        part2 = parts2[i] if i < len(parts2) else 0
        if part1 < part2:
            return 1  # aelter
        elif part1 > part2:
            return 2  # neuer
    return 0  # gleich

