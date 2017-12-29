"""
    This script:
    1) reads all files in current directory and all subdirectories
    2) calc sha256 for all files except *.sha256 
    3) saves it in file yyyymmddhhmmss.sha256 (current date and time)
    4) if there is previous sha256 file - read it and compare with current sha256
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
# import time

# settings

# only compare last 2 early created sha files, don't calc sha
skipShaCheck = False

# when calc sha for a lot of files - it is usual to commit progress periodicaly
# if progress file exists when running script - user got a possibility to resume
# when sha calc is over - progress file will be deleted
# !warning! it is assertion that working directory was not changed since last interuption of script
# in another case - sha results will be inconsistent
progressCommitIntervalSec = 20
progressCommitFileName = 'sha256report.tmp'

# file names in start dir to be skipped (use lower case)
files2skip = ['.tisk', progressCommitFileName]


# internal vars
readErrorFiles = set()
blockSize = 65536
timeStampFormat = "%Y%m%d%H%M%S"
stats = {'dirsCount': 0, 'filesCount': 0,
         'totalSize': 0}  # size is measured in blocks


# Print iterations progress
# (from stackOverflow :)
def printProgressBar(iteration, total, prefix='', suffix='', decimals=1, length=100, fill='█'):
    """
    Call in a loop to create terminal progress bar
    @params:
        iteration   - Required  : current iteration (Int)
        total       - Required  : total iterations (Int)
        prefix      - Optional  : prefix string (Str)
        suffix      - Optional  : suffix string (Str)
        decimals    - Optional  : positive number of decimals in percent complete (Int)
        length      - Optional  : character length of bar (Int)
        fill        - Optional  : bar fill character (Str)
    """
    percent = ("{0:." + str(decimals) + "f}").format(100 * (iteration / float(total)))
    filledLength = int(length * iteration // total)
    bar = fill * filledLength + '-' * (length - filledLength)
    print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end='\r')
    # Print New Line on Complete
    if iteration == total:
        print()


# filling newSha with file paths
# process statistics (file size in blocks) recursively --> stats
newSha = OrderedDict()
def calcFilesSize(curDir, newSha, stats):
    for fileName in listdir(curDir):
        if curDir == '.':
            fullPath = fileName
        else:
            fullPath = join(curDir, fileName)

        if curDir == '.' and (fileName.lower() in files2skip):
            continue

        if isfile(fullPath):
            if curDir == '.' and fileName.endswith('.sha256'):
                continue

            stats['filesCount'] += 1
            size = math.ceil(os.stat(fullPath).st_size / blockSize)
            newSha[fullPath] = None
            stats['totalSize'] += size
        else:
            stats['dirsCount'] += 1
            calcFilesSize(fullPath, newSha, stats)


# calculate sha256 for file
# if knownSha != None doing a simulation mode and return sha
def sha256Checksum(filename,  blockSize, knownSha=None):
    global curSize  # for progress calculation only
    global lastPercent  # for progress calculation only
    
    if knownSha is None:
        sha256 = hashlib.sha256()
        with open(filename, 'rb') as f:
            for block in iter(lambda: f.read(blockSize), b''):
                sha256.update(block)
                curSize += 1
                curPercent=100*curSize/stats['totalSize']
                # call progressbar update only if decimal digit of percent value is changed
                if int(curPercent*10)>int(lastPercent*10):
                    printProgressBar(curSize, stats['totalSize'], length=50)
                lastPercent=curPercent
        # time.sleep(1)
        return sha256.hexdigest()
    else:
        #simulation
        curSize+=math.ceil(os.stat(filename).st_size / blockSize)
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


def writeShaToFile(fileName,sha256FileText):
    with open(fileName, 'w', encoding='UTF-8') as f:
        f.write('\n'.join(sha256FileText))


startDir = '.'
if not skipShaCheck:
    print('scanning directory tree...')

    # fill newSha keys with paths of files. Datas will be None
    calcFilesSize(startDir, newSha, stats)
    print('files:', stats['filesCount'], ' dirs:', stats[
          'dirsCount'], 'totalSize: ', stats['totalSize'], ' blocks')

    if isfile(progressCommitFileName):
        print('loading results of last interrupted ckeck...')
        loadedSha=loadShaFromFile(progressCommitFileName)
        for filePath,sha in newSha.items():
            if (sha is None) and (filePath in loadedSha):
                newSha[filePath]=loadedSha[filePath]
        del loadedSha

    print('calculating sha256 ...')
    curSize = 0
    lastPercent = 0 
    lastTime = datetime.now()
    sha256FileText = []
    for filePath, sha in newSha.items():
        try:
            sha = sha256Checksum(filePath, blockSize, knownSha=sha)
        except PermissionError:
            print('file read failed: ' + filePath)
            readErrorFiles.add(filePath)
        newSha[filePath] = sha
        sha256FileText += [sha + ' *' + filePath]

        # after calc sha256 of every file check time form last commit of
        # progress and make a commit if need
        curTime = datetime.now()

        if (curTime - lastTime).total_seconds() > progressCommitIntervalSec:
            writeShaToFile(progressCommitFileName, sha256FileText)
            lastTime = curTime


    print("save sha256 result to file")
    baseFileName = datetime.strftime(datetime.now(), timeStampFormat)
    newShaFileName = baseFileName + '.sha256'
    writeShaToFile(newShaFileName, sha256FileText)
    del sha256FileText

    # delete temporally progress filename
    if isfile(progressCommitFileName):
        os.remove(progressCommitFileName)


print('detecting and loading sha256 files...')
suitableFileNames = []
for fileName in listdir(startDir):
    if isfile(fileName) and len(fileName) == 21 and fileName.endswith('.sha256') and (fileName[:-7]).isdigit():
        suitableFileNames += [fileName]
suitableFileNames.sort()

if not skipShaCheck:
    if newShaFileName in suitableFileNames:
        i = suitableFileNames.index(newShaFileName) - 1
    else:
        i = -1
else:
    i = len(suitableFileNames) - 2

if i >= 0:
    oldSha = loadShaFromFile(suitableFileNames[i])
    if skipShaCheck:
        # if we skipped sha check - just load 2 last files
        newSha = loadShaFromFile(suitableFileNames[i + 1])
        # filename without .sha256 extension
        baseFileName = suitableFileNames[i + 1][:-7]
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
changedFiles = set(
    {file: None for file in presentFiles if newSha[file] != oldSha[file]})


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
