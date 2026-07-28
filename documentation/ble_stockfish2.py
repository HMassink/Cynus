# -*- coding: utf-8 -*-
import asyncio
from bleak import BleakClient, BleakScanner
from bleak.backends.characteristic import BleakGATTCharacteristic
import threading
from stockfish import Stockfish
from stockfish import StockfishException

stockfish = Stockfish(path=".\stockfish_20011801_x64.exe")

stockfish.update_engine_parameters({"Hash": 2048}) # Gets stockfish to use a 2GB hash table.

stockfish.set_skill_level(15)
stockfish.set_elo_rating(1350)
stockfish.set_depth(15)

#设备的Characteristic UUID
par_notification_characteristic="FFF1"
#设备的MAC地址
device_addr = ["", "", "", "", "", "", "", "", "", ""]
device_cnt = 0
par_device_addr = " "
get_fen = False
main_running = True
fen_str = ""
get_move = False

#监听回调函数，此处为打印消息
def notification_handler(characteristic: BleakGATTCharacteristic, data: bytearray):
    print("rev data:",data)
    if data.startswith(b"fen:"):
        global get_fen
        global fen_str
        get_fen=True
        fen_str = data[5:len(data)-2]
        #print("start with fen:", fen_str)
    elif data.startswith(b"get move"):
        global get_move
        get_move = True
    #print("fen:", get_fen)

send_str=bytearray([0x68,0x69,0x20,0x77,0x6F,0x72,0x6C,0x64,0x0A,0x0D])

user_input = ""
def get_input():
    global main_running
    while main_running:
        global user_input
        user_input = input("# ")
        #print(f"You entered: {user_input}")

async def main():
    print("starting scan...")
    global main_running
    global device_addr
    global device_cnt
    devices = await BleakScanner.discover()
    for d in devices:   #d为类，其属性有：d.name为设备名称，d.address为设备地址
        global par_device_addr
        device_name = str(d.name)
        if device_name.startswith(("CYNUS-", "CMR")):
            device_addr[device_cnt] = d.address       
            print(device_cnt, ": ", d)
            device_cnt =  device_cnt + 1    

    if device_cnt < 1:
        print("could not find device")
        return

    if device_cnt == 1 :
        input_str = 0
    else :
        input_str = input("input:")
    par_device_addr = device_addr[int(input_str)]
    print ("try to connect to device:" + par_device_addr)

    #基于MAC地址查找设备
    device = await BleakScanner.find_device_by_address(
        par_device_addr, cb=dict(use_bdaddr=False)  #use_bdaddr判断是否是MOC系统
    )
    if device is None:
        print("could not find device with address:", par_device_addr)
        return

    #事件定义
    #disconnected_event = asyncio.Event()

    #def disconnected_callback(client):
    #    print("Disconnected callback called!")
    #    disconnected_event.set()

    #print("connecting to device...")
    #async with BleakClient(device,disconnected_callback=disconnected_callback) as client:
    async with BleakClient(device) as client:
        print("connected")
        await client.start_notify(par_notification_characteristic, notification_handler)      
        #await disconnected_event.wait()       #休眠直到设备断开连接，有延迟。此处为监听设备直到断开为止  

        input_thread = threading.Thread(target=get_input)
        input_thread.start()
        i = 1
        while i < 10000:   
            global get_fen         
            #print("get_fen:", get_fen)
            if get_fen:   
                global fen_str
                # print("get a fen:", fen_str)
                # cur_fen1 = fen_str.decode('utf-8') + " b KQkq - 0 15"
                cur_fen1 = fen_str.decode('utf-8') + " b - - 0 15"
                print("cur_fen1:", cur_fen1)      
                stockfish.set_fen_position(cur_fen1)  
                #stockfish.set_fen_position(fen_str.encode('UTF-8'))
                #stockfish.set_fen_position("rnbqkbnr/pppp1ppp/4p3/8/4P3/8/PPPP1PPP/RNBQKBNR")  
                # cur_fen2 = stockfish.get_fen_position()
                # print(cur_fen2)                
                # stockfish.flip()
                # stockfish.get_fen_position()
                # print(cur_pos)                

                board_visual = stockfish.get_board_visual()
                print(board_visual)
                get_fen = False

                global get_move
                if get_move == True :
                    try:
                        # Evaluation routine
                        best_move = stockfish.get_best_move_time(1000)
                    except StockfishException:
                        # Error handling    
                        print("stockfish get best move error")
                    print("best move: ", best_move)
                    get_move = False
                    await client.write_gatt_char(par_notification_characteristic, b'move ' + best_move.encode('UTF-8') + b'\r\n')


            global user_input              
            #user_input=input("input:")
            if user_input != "":
                print(f"You entered: {user_input}")
                #print(user_input)
                if user_input == "quit" :
                    print ("quit the program")
                    break;
                cmd=user_input.encode('utf-8')
                await client.write_gatt_char(par_notification_characteristic, cmd + b'\r\n')
                #get_fen = False
                user_input = ""
            i += 1
            await asyncio.sleep(0.5)           #每休眠1秒发送一次

        await client.stop_notify(par_notification_characteristic)
    #断开连接事件回调，当设备断开连接时，会触发该函数，存在一定延迟
    main_running = False

    stockfish.send_quit_command()

    print("end...")

asyncio.run(main())