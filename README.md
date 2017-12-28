# sha256report
compares previous and current state for all files in current directory

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
