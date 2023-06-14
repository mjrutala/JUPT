import cdflib
from astropy.time import Time, TimeDelta
import datetime
import numpy as np
import matplotlib.colors as colors
from tqdm import tqdm
import os
from glob import glob

def PathsFromTimeDifference(t1, t2, pathFormat):
    # Inputs are time in format "2022-06-01T00:00:00"
    # Outputs a list of paths to the data containing the time
    date1, time1 = t1.split("T")
    date2, time2 = t2.split("T")

    year1, month1, day1 = date1.split("-")
    year2, month2, day2 = date2.split("-")

    hours1, minutes1, seconds1 = time1.split(":")

    startDate = datetime.date(int(year1), int(month1), int(day1)) 
    # NOTE: Waves files start from 00:01:09 on each day and end on 00:01:08 the next day meaning to plot from 00:00:00 we need the day before's data.
    if hours1 == "00" and int(minutes1) <= 1 and int(seconds1) < 10:
        startDate = startDate - datetime.timedelta(days=1)

    endDate = datetime.date(int(year2), int(month2), int(day2))

    pathExtensions = []

    if startDate == endDate:
        pathExtensions.append(startDate.strftime(pathFormat))
    
    else:
        for date in DateRange(startDate, endDate):
            pathExtension = date.strftime(pathFormat)
            pathExtensions.append(pathExtension)

    return pathExtensions

def DownloadWavesData(dataPath, downloadPath, timeFrame):

    pathList = [f"{downloadPath}{extension}" for extension in PathsFromTimeDifference(timeFrame[0], timeFrame[1], "%Y/%m/jno_wav_cdr_lesia_%Y%m%d_v02.cdf")]
    print(f"Downloading Waves files from {downloadPath} to {dataPath}\n")
    for path in tqdm(pathList):
        os.system(f"wget -r -q -nd -nv -np -nH -N -P {dataPath} {path}")


def LoadCdfFiles(dataDirectory, measurements):
    # Inputs are a directory containing the files to be loaded and a list of the measurements to be pulled from the files.

    # NEED TO CHECK TO ONLY LOAD FILES WITHIN THE TIME FRAME, REUSE PATHSFROMTIMEDIFFERENCE?

    print(f"Loading CDF files from {dataDirectory}")
    
    filePaths = glob(f"{dataDirectory}*.cdf") # returns a list of downloaded file paths (unsorted)
    filePaths.sort() # Because the date in in the file is in format yyyymmdd it can be sorted numerically.

    filesInfoList = []

    for filePath in tqdm(filePaths):
        file = cdflib.CDF(filePath)

        fileInfo = dict()
        for measurment in measurements:
            measurmentData = file.varget(measurment)
            # measurementUnit = file.varinq(measurment)["Data_Type_Description"]

            fileInfo[measurment] = measurmentData
        
        filesInfoList.append(fileInfo)

    return filesInfoList

def DeleteData(dataDirectory):
    os.system(f"rm {dataDirectory}*.cdf")
    
def PlotData(fig, ax, timeFrame, dataDirectory, vmin=False, vmax=False, plotEphemeris=False, downloadNewData=True):
    # Takes one of the subplot axes as input
    
    print("Retrieving waves data...")

    if downloadNewData == True:
        DownloadWavesData(dataDirectory, "https://maser.obspm.fr/repository/juno/waves/data/l3a_v02/data/cdf/", timeFrame) # Path should be in format .../data/

    filesWithInfo = LoadCdfFiles(dataDirectory, ["Epoch", "Frequency", "Data"])

    # Initialise lists to put the data into
    time = []
    frequency = []
    data = []

    for i, fileInfo in enumerate(filesWithInfo): # enumerate could be computationally expensive here. Perhaps change to a boolean test as it is only a one time use?
        # Next we must contract the lists to the timeframe we have selected.
        if i==0:
            sliceStart = 0
            
            print("Shortening data to match time frame. This may take some time")
            print("Finding start point...")
            for j, t in tqdm(enumerate(fileInfo["Epoch"]), total=len(fileInfo["Epoch"])): # this is quite slow, takes around 30 seconds
                t = Time(t, format="cdf_tt2000")
                t.format="datetime"
                tFrame = Time(timeFrame[0], format = "isot")
                tFrame.format="datetime"

                if t >= tFrame:
                    break
                sliceStart = j
            
            print("Found start point")
            time.extend(fileInfo["Epoch"][sliceStart:])
            data.extend(fileInfo["Data"][sliceStart:])

        elif i==len(filesWithInfo)-1:
            sliceEnd = 0
            
            print("Finding end point...")
            for j, t in tqdm(enumerate(fileInfo["Epoch"]), total=len(fileInfo["Epoch"])): # Similarly very slow around 30 seconds
                t = Time(t, format="cdf_tt2000")
                t.format="datetime"
                tFrame = Time(timeFrame[1], format = "isot")
                tFrame.format="datetime"

                if t >= tFrame:
                    break
                sliceEnd = j
                    
            print("Found end point")
            time.extend(fileInfo["Epoch"][:sliceEnd])            
            data.extend(fileInfo["Data"][:sliceEnd])
        
        else:
            time.extend(fileInfo["Epoch"])
            data.extend(fileInfo["Data"])
        
    # Reformat time into something we can use
    wavesTime = Time(time, format="cdf_tt2000")
    wavesTime.format = "isot"
    
    wavesFrequencies = filesWithInfo[0]["Frequency"]

    wavesData = np.transpose(data)

    # Calibrating by dividing by 377 Ohms
    for frequencyRow in wavesData:
        for flux in frequencyRow:
            flux = flux / 377

    # Adapted code taken from Corentin
    index_array = range(len(wavesTime))

    if vmin == False and vmax == False:
        vmin=np.quantile(wavesData,0.05)
        vmax=np.quantile(wavesData,0.95)
    
    image = ax.pcolormesh(index_array, wavesFrequencies, wavesData, cmap="Spectral_r", norm=colors.LogNorm(vmin, vmax))
    ax.set_yscale("log")
    
    ax.set_ylabel("Frequency (kHz)")
    ax.set_xlabel("Time (s)")

    # cax = divider.append_axes("right", size=0.15, pad=0.2)

    fig.colorbar(image, extend='both', shrink=0.9,ax=ax, label="Flux Density (W m$^{-2}$ Hz$^{-1}$)")

    DeleteData(dataDirectory)


def DateRange(start_date, end_date):
    for n in range(int((end_date - start_date).days) + 1): # NOTE: adding +1 to include endDate
        yield start_date + datetime.timedelta(n)
