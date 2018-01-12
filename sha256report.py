"""
    This script:
    1) reads all files in current directory and all subdirectories
    2) calc sha256 for all files except *.sha256
    3) saves it in file yyyymmddhhmmss.sha256 (current date and time)
    4) if there is prev sha256 file - read it and compare with current sha256
    5) save compare results to files:
        yyyymmddhhmmss.added.sha256
        yyyymmddhhmmss.deleted.sha256
        yyyymmddhhmmss.changed.sha256
        yyyymmddhhmmss.error.sha256
        (these files not contains sha256, only files list)
"""

import os
import hashlib
import math
import sys
from os.path import isfile, join
from os import listdir
from datetime import datetime
from collections import OrderedDict

settings = {
    # compare current files state witn last created sha files, don't calc sha
    'skipShaCheck': False,
    'blockSize': 65536,
    'timeStampFormat': "%Y%m%d%H%M%S",
    'progressCommitFileName': 'sha256report.tmp',
    # file names in start dir to be skipped (use lower case)
    'files2skip': ['.tisk', 'sha256report.tmp'],
    # when calc sha for big files - it is usual to commit progress periodicaly
    # if progress file exists - user got a possibility to resume
    # when sha calc is over - progress file will be deleted
    # !warning!
    # it is assertion that directory was not changed since last interuption
    # in another case - sha results will be inconsistent
    'progressCommitIntervalSec': 20
}

# current statistics storage
stats = {'dirsCount': 0,
         'filesCount': 0,
         'totalSize': 0,  # size is measured in blocks
         'curSize': 0,
         'lastPercent': 0}

# internal vars
readErrorFiles = set()


# Print iterations progress
# (from stackOverflow :)
def printProgressBar(iteration, total, prefix='', suffix='',
                     decimals=1, length=100, fill='█'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(
        100 * (iteration / float(total))
        )
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end='\r')
    # Print New Line on Complete
    if iteration == total:
        print()


# return OrderedDict with paths of files like {'path':None}
# process statistics to vStats
def calcFilesSize(curDir: str, vStats: dict,
                  settings: dict, vRes=OrderedDict()):
    for fileName in listdir(curDir):
        if curDir == '.':
            fullPath = fileName
        else:
            fullPath = join(curDir, fileName)

        if curDir == '.' and (fileName.lower() in settings['files2skip']):
            continue

        if isfile(fullPath):
            if curDir == '.' and fileName.endswith('.sha256'):
                continue

            vStats['filesCount'] += 1
            size = math.ceil(os.stat(fullPath).st_size / settings['blockSize'])
            vStats['totalSize'] += size
            vRes[fullPath] = None
        else:
            vStats['dirsCount'] += 1
            calcFilesSize(fullPath, vStats, settings, vRes)
    return vRes


# calculate sha256 for file
# if knownSha != None doing a simulation mode and return sha
def sha256Checksum(filename,  blockSize, stats, knownSha=None):
    if knownSha is None:
        # not a simulation, calc sha256
        sha256 = hashlib.sha256()
        with open(filename, 'rb') as f:
            for block in iter(lambda: f.read(blockSize), b''):
                sha256.update(block)
                stats['curSize'] += 1
                curPercent = 100 * stats['curSize'] / stats['totalSize']
                # call progressbar update only if 1st decimal digit
                # of percent value is changed
                if int(curPercent * 10) > int(stats['lastPercent'] * 10):
                    printProgressBar(
                        stats['curSize'],
                        stats['totalSize'],
                        length=50)
                stats['lastPercent'] = curPercent
        return sha256.hexdigest()
    else:
        # simulation
        stats['curSize'] += math.ceil(os.stat(filename).st_size / blockSize)
        return knownSha


def loadShaFromFile(fileName):
    res = OrderedDict()
    with open(fileName, 'r', encoding='UTF-8') as f:
        for line in f:
            sha, fileNamePath = line.split(' *')
            if fileNamePath.endswith('\n'):
                fileNamePath = fileNamePath[:-1]
            res[fileNamePath] = sha
    return res


def writeShaToFile(fileName, sha256FileText):
    with open(fileName, 'w', encoding='UTF-8') as f:
        f.write('\n'.join(sha256FileText))


startDir = '.'
print('scanning directory tree...')

# get OrderedDict with paths of files like {'path':None}
newSha: OrderedDict = calcFilesSize(startDir, stats, settings)
print('files:', stats['filesCount'], ' dirs:', stats['dirsCount'],
      'totalSize: ', stats['totalSize'], ' blocks')


if not settings['skipShaCheck']:
    if isfile(settings['progressCommitFileName']):
        print('loading results of last interrupted ckeck...')
        loadedSha = loadShaFromFile(settings['progressCommitFileName'])
        for filePath, sha in newSha.items():
            if (sha is None) and (filePath in loadedSha):
                newSha[filePath] = loadedSha[filePath]
        del loadedSha

    print('calculating sha256 ...')
    curSize = 0
    lastPercent = 0
    lastTime = datetime.now()
    sha256FileText = []
    for filePath, sha in newSha.items():
        try:
            sha = sha256Checksum(
                filePath,
                settings['blockSize'],
                stats,
                knownSha=sha)
        except PermissionError:
            print('file read failed: ' + filePath)
            readErrorFiles.add(filePath)
        newSha[filePath] = sha
        sha256FileText += [sha + ' *' + filePath]

        # after calc sha256 of every file check time form last commit of
        # progress and make a commit if need
        curTime = datetime.now()

        if (curTime - lastTime).total_seconds() > \
                settings['progressCommitIntervalSec']:
            writeShaToFile(settings['progressCommitFileName'], sha256FileText)
            lastTime = curTime

# calc baseFileName AFTER sha calc process end
baseFileName = datetime.strftime(datetime.now(), settings['timeStampFormat'])
newShaFileName = baseFileName + '.sha256'

if not settings['skipShaCheck']:
    print("save sha256 result to file")
    writeShaToFile(newShaFileName, sha256FileText)
    del sha256FileText

    # delete temporally progress filename
    if isfile(settings['progressCommitFileName']):
        os.remove(settings['progressCommitFileName'])


print('detecting and loading sha256 files...')
suitableFileNames = []
for fileName in listdir(startDir):
    if isfile(fileName) and \
            len(fileName) == 21 and \
            fileName.endswith('.sha256') and \
            (fileName[:-7]).isdigit():
        suitableFileNames += [fileName]
suitableFileNames.sort()

if not settings['skipShaCheck']:
    # search for previous sha file name (for current sha file)
    if newShaFileName in suitableFileNames:
        i = suitableFileNames.index(newShaFileName) - 1
    else:
        # not found
        i = -1
else:
    # "current" cha file is absent, so use last found sha file as previous
    i = len(suitableFileNames)-1


if i >= 0:
    oldSha = loadShaFromFile(suitableFileNames[i])
else:
    print('sha256 file(s) not found, exiting')
    sys.exit()

# now we have:
# 1) newSha & oldSha structures to compare
# 2) baseFileName string for naming files with compare results
print('comparing old sha256 and new sha256 files...')
newShaSet = set(newSha)
oldShaSet = set(oldSha)
presentFiles = newShaSet & oldShaSet
deletedFiles = oldShaSet - newShaSet
addedFiles = newShaSet - oldShaSet

if not settings['skipShaCheck']:
    changedFiles = set(
        {file: None for file in presentFiles if newSha[file] != oldSha[file]})
else:
    changedFiles = set()

print('writing compare results...')
if addedFiles:
    with open(baseFileName + '.added.sha256', 'w', encoding='UTF-8') as f:
        f.write('\n'.join(sorted(list(addedFiles))))
if deletedFiles:
    with open(baseFileName + '.deleted.sha256', 'w', encoding='UTF-8') as f:
        f.write('\n'.join(sorted(list(deletedFiles))))
if changedFiles:
    with open(baseFileName + '.changed.sha256', 'w', encoding='UTF-8') as f:
        f.write('\n'.join(sorted(list(changedFiles))))
if readErrorFiles:
    with open(baseFileName + '.error.sha256', 'w', encoding='UTF-8') as f:
        f.write('\n'.join(sorted(list(readErrorFiles))))


print('all done! Added:', len(addedFiles), ' deleted:', len(deletedFiles),
      ' changed:', len(changedFiles), ' errors:', len(readErrorFiles))
print('press Enter to exit')
input()
