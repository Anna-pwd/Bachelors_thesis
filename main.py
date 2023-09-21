#System Kontroli Dostepu z Rejestrem Zdarzen
#Anna Bagniewska
#Politechnika Bydgoska, Wydzial Telekomunikacji, Informatyki i Elektrotechniki
#Praca Inzynierska - Styczen 2023

#Importowanie bibliotek
import machine
import network #WiFi
import socket
import usocket
import urequests as requests
from secrets import secrets #hasla
from umqtt.simple import MQTTClient #MQTT Broker
from machine import Pin #Definicja portow
from machine import I2C #Komunikacja I2C
from ds3231_i2c import DS3231_I2C #Modul zegara czasu rzeczywistego
from mfrc522 import MFRC522 #RFID
import utime #Czas
import time #Czas
from utime import sleep #Czas, ulatwienie kodu

#Logowanie do sieci
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
ssid2 = secrets['ssid']
pw2 = secrets['pw']
wlan.connect(ssid2,pw2)

time.sleep(5)
print(wlan.isconnected())

#Dane logowania do HiveMQ
client_id = b'anna_raspberry_pi_pico_w'
mqtt_server = b'9c9f8e45006146f5908f5550ae759b15.s2.eu.hivemq.cloud'
port = 0
user = b'your id'
password = b'your password'
keepalive = 7200
ssl = True
ssl_params = {'server_hostname':'9c9f8e45006146f5908f5550ae759b15.s2.eu.hivemq.cloud'}
global topic_pub
topic_pub = b'SKD2023'

#Przypisanie portow - RTC
rtc = machine.I2C(0,sda=Pin(16), scl=Pin(17))

#Przypisanie portow - RFID
reader = MFRC522(spi_id=0,sck=2,miso=4,mosi=3,cs=1,rst=0)

#Przypisanie portow - LED
red = Pin(13, Pin.OUT)
green = Pin(12, Pin.OUT)
yellow = Pin(11, Pin.OUT)

#Przypisanie portow - przekaznik
relay = Pin(18, Pin.OUT)

#Przypisanie portow - buzzer
buzzer = Pin(15, Pin.OUT)

#Przypisanie portow - przycisk wyjscia
button = Pin(5, Pin.IN, Pin.PULL_DOWN)

#Przypisanie portow - czujnik drzwi
reedswitch = Pin(10, Pin.IN, Pin.PULL_UP)

#Wypisanie uzywanych adresow urzadzen I2C oraz podstawowych informacji
print("RTC I2C Address : " + hex(rtc.scan()[0]).upper())
print("RTC I2C Configuration: " + str(rtc)) 
ds = DS3231_I2C(rtc)

#Ustawianie czasu. Po jednokrotnym wykonaniu nalezy zakomentowac 2 ponizsze linie
#current_time = b'\x00\x34\x14\x04\x11\x01\x23' # sekundy\minuty\godziny\dzientygodnia\dzien\miesiac\rok
#ds.set_time(current_time)

#Ustawienie nazwy dni tygodnia
w = ["Sunday","Monday","Tuesday","Wednesday","Thurday","Friday","Saturday"];

#Wyswietlenie aktualnej daty
t = ds.read_time()
#print("Date: %02x/%02x/20%x" %(t[4],t[5],t[6]))
#print(" Time: %02x:%02x:%02x" %(t[2],t[1],t[0]))

#Deklaracja zmiennych globalnych, przypisanie wartosci
global button_pressed
global reedswitch_opened
global authorised

button_pressed = False
reedswitch_opened = False
authorised = False

#Definicja funkcji wywoływanej do obslugi polaczenia WLAN
def mqtt_connect():
    client = MQTTClient(client_id, mqtt_server, port, user, password, keepalive, ssl, ssl_params)
    client.connect()
    print('Connected to %s MQTT Broker'%(mqtt_server))
    return client

def reconnect():
    print('Failed to connect to the MQTT Broker. Reconnecting...')
    time.sleep(5)
    machine.reset()

#Wylapywanie wyjatkow
try:
    client = mqtt_connect()
    
except OSError as e:
    reconnect()

#Definicja funkcji wywolywanej przerwaniem kontaktronem
def reedswitch_handler(reedswitch):
    global reedswitch_opened
    if not reedswitch_opened:
        reedswitch_opened = True

#ustalenie przerwania w przypadku otworzenia drzwi bez zgody
reedswitch.irq(trigger=machine.Pin.IRQ_RISING, handler=reedswitch_handler)

#Wylaczenie wszystkich odbiornikow
red.value(0)
green.value(0)
yellow.value(0)
relay.value(0)
buzzer.value(0)

#Start RFID
print("Bring TAG closer...")
print("")
buzzer.value(1)
utime.sleep(1)
buzzer.value(0)

#Wiadomosc powitalna
read_date = (" Data: %02x/%02x/20%x" %(t[4],t[5],t[6]))
read_time = ("Godzina: %02x:%02x:%02x" %(t[2],t[1],t[0]))
date_time = (read_date+' '+read_time)
topic_msg = (b'Uruchomiono system -' + date_time)
client.publish(topic_pub, topic_msg)

while True:
#Wprowadzenie zmiennych globalnych
    global authorised
    global reedswitch_opened
    global authorised
    global topic_pub

#Obsluga TAGow    
    reader.init()
    (stat, tag_type) = reader.request(reader.REQIDL)
    if stat == reader.OK:
        (stat, uid) = reader.SelectTagSN()
        if stat == reader.OK:
            card = int.from_bytes(bytes(uid),"little",False)

            if ((card == 786954480) or (card == 3602143703)):
                print("Card ID: "+ str(card)+" PASS: Green Light On")
                authorised = True
                red.value(0)
                green.value(1)
                yellow.value(0)
                relay.value(1)
                utime.sleep(3)
                red.value(0)
                green.value(0)
                yellow.value(0)
                relay.value(0)             

            else:
                print("Card ID: "+str(card)+" UNKNOWN CARD! Red Light On, Sound On")
                authorised = False
                red.value(1)
                green.value(0)
                yellow.value(0)
                buzzer.value(1)
                t = ds.read_time()
                read_date = (" Date: %02x/%02x/20%x" %(t[4],t[5],t[6]))
                read_time = ("Time: %02x:%02x:%02x" %(t[2],t[1],t[0]))
                date_time = (read_date+' '+read_time)
                topic_msg = (b'Nieautoryzowana proba otworzenia drzwi -' + date_time)
                client.publish(topic_pub, topic_msg)
                utime.sleep(1)
                red.value(0)
                green.value(0)
                yellow.value(0)
                buzzer.value(0)
                
#Obsluga kontaktronu                
    if reedswitch_opened == True:
        global authorised
        if ((reedswitch.value() == 1) and (authorised == False)):
            relay.value(0)
            red.value(1)
            buzzer.value(1)
            print(date_time)
            t = ds.read_time()
            read_date = (" Date: %02x/%02x/20%x" %(t[4],t[5],t[6]))
            read_time = ("Time: %02x:%02x:%02x" %(t[2],t[1],t[0]))
            date_time = (read_date+' '+read_time)
            #Stworzenie GET Request dla IFTTT
            ifttt_url = 'https://maker.ifttt.com/trigger/the_door_opened/with/key/'+secrets['ifttt_key']
            request = requests.get(ifttt_url)
            request.close()
            #Dane dla HiveMQ
            topic_msg = (b'Otworzono drzwi bez autoryzacji -' + date_time)
            client.publish(topic_pub, topic_msg)
            utime.sleep(5)
            if reedswitch.value() == 1:
                red.value(1)
            else:
                red.value(0)
                
        elif ((reedswitch.value() == 1) and (authorised == True)):
            t = ds.read_time()
            read_date = (" Date: %02x/%02x/20%x" %(t[4],t[5],t[6]))
            read_time = ("Time: %02x:%02x:%02x" %(t[2],t[1],t[0]))
            date_time = (read_date+' '+read_time)
            topic_msg = (b'Otworzono drzwi z autoryzacją -' + date_time)
            client.publish(topic_pub, topic_msg)
            relay.value(0)
            utime.sleep(10)
            buzzer.value(1)
            utime.sleep(1)
            buzzer.value(0)
            while reedswitch.value() == 1:
                red.value(1)
                green.value(0)
                for i in range(1, 20):
                    red.toggle()
                    utime.sleep(0.5)
                buzzer.value(1)
                utime.sleep(0.5)
                buzzer.value(0)
            authorised = False
            
        elif ((reedswitch.value() == 0) and (authorised == True)):
            utime.sleep(1)
            relay.value(0)
            buzzer.value(0)
            authorised = False
        else:
            relay.value(0)
            red.value(0)
            buzzer.value(0)
            reedswitch_opened = False
            authorised = False
    else:
        relay.value(0)
        red.value(0)
        buzzer.value(0)
        reedswitch_opened = False
        authorised = False
        
#Obsluga przycisku wyjscia
    if button.value() == 1:
        global authorised
        authorised = True
        yellow.value(1)
        buzzer.value(1)
        relay.value(1)
        for j in range(1, 200000):
            yellow.value(1)
            buzzer.value(1)
            relay.value(1)
        yellow.value(0)
        buzzer.value(0)
        relay.value(0)
        utime.sleep(0.5)
    else:
        yellow.value(0)
        buzzer.value(0)
        relay.value(0)
        authorised = False
else:
    yellow.value(0)
    buzzer.value(0)
    relay.value(0)
    global button_pressed
    button_pressed = False
    authorised = False
