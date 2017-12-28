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
import time
from os.path import isfile,join,dirname
from os import listdir
from datetime import datetime

newSha={}
oldSha={}
readErrorFiles=set()
blockSize=65536
timeStampFormat="%Y%m%d%H%M%S"
stats={'dirsCount':0, 'filesCount':0,'totalSize':0} # size is measured in blocks

# Print iterations progress
# (from stackOverflow :)
def printProgressBar (iteration, total, prefix = '', suffix = '', decimals = 1, length = 100, fill = '█'):
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
    print('\r%s |%s| %s%% %s' % (prefix, bar, percent, suffix), end = '\r')
    # Print New Line on Complete
    if iteration == total: 
        print()


# filling newSha with file paths
# process statistics (file size in blocks) recursively --> stats
def calcFilesSize(curDir,newSha,stats):
    for fileName in listdir(curDir):
        if curDir=='.':
            fullPath=fileName
        else:
            fullPath=join(curDir,fileName)

        if isfile(fullPath):
            if curDir=='.' and fileName.endswith('.sha256'):
                continue

            stats['filesCount']+=1
            size=math.ceil(os.stat(fullPath).st_size/blockSize)
            newSha[fullPath]=None
            stats['totalSize']+=size
        else:
            stats['dirsCount']+=1
            calcFilesSize(fullPath,newSha,stats)


# calculate sha256 for directory tree recursively
# no error handling
def sha256Checksum(filename,  blockSize):
    global curSize #for progress calculation only 
    global curPercent #for progress calculation only
    sha256 = hashlib.sha256()
    with open(filename, 'rb') as f:
        for block in iter(lambda: f.read(blockSize), b''):
            sha256.update(block)
            curSize+=1
            printProgressBar (curSize, stats['totalSize'],length=50)
            # newPercent=math.ceil(100*curSize/stats['totalSize'])
            # if newPercent>curPercent:
            #     curPercent=newPercent
            #     print(curPercent,'%')
    return sha256.hexdigest()


print('scanning directory tree...')
startDir='.'
calcFilesSize(startDir,newSha,stats)
print('files:',stats['filesCount'],' dirs:',stats['dirsCount'],'totalSize: ',stats['totalSize'],' blocks')


print('calculating sha256 ...')
curSize=0
curPercent=0
sha256FileText=[]
for fileName,fileData in newSha.items():
    try:
        sha256=sha256Checksum(fileName,blockSize)
    except PermissionError:
        print('file read failed: '+fileName)
        readErrorFiles.add(fileName)
    newSha[fileName]=sha256
    sha256FileText+=[sha256+' *'+fileName]


print("save sha256 result to file")
baseFileName=datetime.strftime(datetime.now(),timeStampFormat)
newShaFileName=baseFileName+'.sha256'
with open(newShaFileName,'w',encoding='UTF-8') as f:
    f.write('\n'.join(sha256FileText))
sha256FileText=None


print('detecting and loading old sha256 file...')
suitableFileNames=[]
for fileName in listdir(startDir):
    if isfile(fileName) and len(fileName)==21 and fileName.endswith('.sha256') and (fileName[:-7]).isdigit():
        suitableFileNames+=[fileName]
suitableFileNames.sort()
oldShaFileName=None

if newShaFileName in suitableFileNames:
    i=suitableFileNames.index(newShaFileName)-1
    if i>=0:
        oldShaFileName=suitableFileNames[i]

if oldShaFileName is None:
    print('old sha256 file not found, exiting')
    sys.exit()


print('loading old sha256 file...')
with open(oldShaFileName,'r',encoding='UTF-8') as f:
    for line in f:
        sha,file=line.split(' *')
        if file.endswith('\n'):
            file=file[:-1]
        oldSha[file]=sha


print('comparing old sha256 and new sha256 files...')
newShaSet=set(newSha)
oldShaSet=set(oldSha)
presentFiles=sorted(list(newShaSet & oldShaSet))
deletedFiles=sorted(list(oldShaSet-newShaSet))
addedFiles=newShaSet-oldShaSet
changedFiles=sorted(list({file:None for file in presentFiles if newSha[file] != oldSha[file]}))
readErrorFiles=sorted(list(readErrorFiles))


print('writing compare results...')
if addedFiles:
    with open(baseFileName+'.added.sha256','w',encoding='UTF-8') as f:
        f.write('\n'.join(addedFiles))
if deletedFiles:
    with open(baseFileName+'.deleted.sha256','w',encoding='UTF-8') as f:
        f.write('\n'.join(deletedFiles))
if changedFiles:
    with open(baseFileName+'.changed.sha256','w',encoding='UTF-8') as f:
        f.write('\n'.join(changedFiles))
if readErrorFiles:
    with open(baseFileName+'.error.sha256','w',encoding='UTF-8') as f:
        f.write('\n'.join(readErrorFiles))
print('all done! Added:',len(addedFiles),' deleted:',len(deletedFiles),' changed:',len(changedFiles),' errors:',len(readErrorFiles) )
print('press Enter to exit')
input()
