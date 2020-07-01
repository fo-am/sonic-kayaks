import os
import glob
import time
import osc
import smbus
import struct
from wobble import *

class auto_cali:
    def __init__(self):
        self.mini = 9999
        self.maxi = 0

    def update(self,v):
        #gradual recalibration
        self.maxi-=0.01
        self.mini+=0.01
        if v>self.maxi: self.maxi=v
        if v<self.mini: self.mini=v    
        r = float(self.maxi-self.mini)
        print(str(r)+" "+str(self.mini)+" "+str(self.maxi))            
        if r>0:
            return (v-self.mini)/r
        else:
            return 0

# reads the turbidity and particulate matter
# from the arduino, logs it and sends it to pure data

bus = smbus.SMBus(1)
log_path = "/home/pi/stick/sonickayak/logs/sensors.csv"

#record output messages to a log file
def log(text):
    adv_log = open(log_path, "a")
    adv_log.write(text + "\n")
    adv_log.close()


def check_pm(dat):
    if dat[0]==0x42 and dat[1]==0x4d or \
       dat[1]==0x42 and dat[0]==0x4d:
        return True
    return False

def check_temp(dat):
    try:
        if bytearray(dat)[0:4].decode('utf-8')=="temp":
            return True
        return False
    except:
        return False


def read_arduino_block(i2c_addr,samples):
    try:
        dat = bus.read_i2c_block_data(i2c_addr,0,32)    

        if check_pm(dat):
            d = struct.unpack(">HHHHHHHHHHHHHHHH",bytearray(dat))
            samples["air"]=d
            return samples
        
        if check_temp(dat):
            d = struct.unpack("<xxxxfxxxxxxxxxxxxxxxxxxxxxxxx",bytearray(dat))
            samples["temp"]=d[0]
            return samples
            
        d = struct.unpack("<BffBffBffxxxxx",bytearray(dat))
        samples[d[0]]=[d[1],d[2]]
        samples[d[3]]=[d[4],d[5]]
        samples[d[6]]=[d[7],d[8]]
        return samples
    except:
        return samples
            
def read_arduino(i2c_addr):
    samples={}
    samples=read_arduino_block(i2c_addr,samples)
    samples=read_arduino_block(i2c_addr,samples)
    samples=read_arduino_block(i2c_addr,samples)
    samples=read_arduino_block(i2c_addr,samples)
    samples=read_arduino_block(i2c_addr,samples)
    return samples
    
log("New session started...")

i2c_addrs=[0x09] # 9 is in the box

# lag & thresh tweaked from test data
temp_wobble=wobble(1.0,0.0000003)
air_wobble=wobble(0.5,1.5)
turbid_wobble=wobble(0.5,4)

def send_soni_osc(delta,temp,air,turbid):
    temp_event=temp_wobble.update(temp,delta)
    air_event=air_wobble.update(air,delta)
    turbid_event=turbid_wobble.update(turbid,delta)

    to_pd=[temp,temp_event.event_type,
           air,air_event.event_type,
           turbid,turbid_event.event_type]
    #print(to_pd)
    osc.Message("/sensors",to_pd).sendlocal(8889)

    
while True:
    for dev_id,i2c_addr in enumerate(i2c_addrs):
        samples = read_arduino(i2c_addr)
        if len(samples)==11:
            line = time.strftime("%Y:%m:%d")+","+\
                   time.strftime("%H:%M:%S")+","

            line+=str(samples["temp"])
            for a in samples["air"]:
                line+=str(a)+","
        
            for l in range(0,8):
                line+=str(samples[l][0])+","                            
            log(line)
            
            send_soni_osc(1,samples["temp"],samples["air"][3],samples[0][0])
            
        else:
            # todo: output i2c error or missing sensors
            print("no samples")
    time.sleep(1)

    
