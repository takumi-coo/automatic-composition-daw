import pygame
import numpy as np
import pretty_midi
import time
import mido
import threading

import pygame.draw

# 初期設定
pygame.init()
SCREEN_WIDTH = 900
SCREEN_HEIGHT = 600
SCREEN_SIZE = (SCREEN_WIDTH, SCREEN_HEIGHT)
pygame.display.set_caption('Simple MIDI DAW')

# Colors
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
GRAY = (200, 200, 200)

GRID_GRAY = (60,60,60)
GRID_GRAY4 = (160,160,160)
GRID_GRAY8 = (190, 190, 190)
GRID_GRAY16 = (190, 190, 190)
GRID_COLOR = [GRID_GRAY,GRID_GRAY4,GRID_GRAY8,GRID_GRAY16]
GRID_COLOR_NUMBER_LIST = [[0,1,1,1],[0,2,1,2,1,2,1,2],[0,3,2,3,1,3,2,3,1,3,2,3,1,3,2,3]]

BARMEASURE_COLOR = (220,220,220)
BARMEASURE_BLIND_COLOR = (150,150,150)

NOTE_COLOR_in = (0, 0, 240)
NOTE_COLOR = (50, 50, 250)  # ノートの色
SCROLLBAR_COLOR = (180, 180, 180)
HANDLE_COLOR = (120, 120, 120)

# Constants
PIANO_WIDTH = 120 #基本ピアノの幅
WHITE_KEY_HEIGHT = 24 #白鍵の高さの高さ
BLACK_KEY_HEIGHT_cd = int(WHITE_KEY_HEIGHT * 7 / 12) #黒鍵c♯d♯の高さ
BLACK_KEY_HEIGHT_fga = int(WHITE_KEY_HEIGHT * 7 / 12) -1 #黒鍵f♯g♯a♯の高さ
NOTE_HEIGHT = int(WHITE_KEY_HEIGHT * 7 / 12) #ノートの高さ
KEY_HEIGHT = [NOTE_HEIGHT,NOTE_HEIGHT+1,NOTE_HEIGHT,NOTE_HEIGHT+1,NOTE_HEIGHT,NOTE_HEIGHT,
              NOTE_HEIGHT,NOTE_HEIGHT-1,NOTE_HEIGHT,NOTE_HEIGHT,NOTE_HEIGHT,NOTE_HEIGHT-1] #鍵盤の高さ
BLACK_KEY_WIDTH = PIANO_WIDTH // 2 #黒鍵の幅
WHITE_KEY_WIDTH = PIANO_WIDTH #白鍵の幅
LOWEST_PITCH = 21 #最低音
HIGHEST_PITCH = 108 #最高音
NOTE_DISPLAY_HEIGHT = SCREEN_HEIGHT #ノートの最高位置
BLACK_KEYS = [1, 3, 6, 8, 10] #黒鍵のノート
WHITE_KEYS = [0, 2, 4, 5, 7, 9, 11] #白鍵のノート
BORDER_WIDTH = 1 #縁
SCROLLBAR_THICKNESS = 20 #スクロールバーの高さ
MIN_SCROLLBAR_THUMB_SIZE = 30 #スクロールバーの持ち手幅
MAX_BAR = 250 #小節上限
BASE_INTERVAL = 80 #基本ピアノロール幅
BAR_MEASURE_WIDTH = SCREEN_WIDTH-SCROLLBAR_THICKNESS 
BAR_MEASURE_HEIGHT = 50

INITIAL_Y = 270

FONTSIZE = 25
FONT = pygame.font.Font(None, FONTSIZE)


# ズームレベルの初期設定
INITIAL_ZOOM_LEVEL = 4
#unit_width = BASE_INTERVAL*INITIAL_ZOOM_LEVEL (1小節の長さ)

# クリックタイミングを記録する変数
last_click_time = 0
double_click_time = 500  # ダブルクリックとみなす時間間隔（ミリ秒）

# MIDIファイルの読み込み
MIDI_FILE = 'output.mid'


def create_midi_file(file_name,tempo):
    # PrettyMIDIオブジェクトの作成
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)

    # ピアノ楽器の追加
    piano = pretty_midi.Instrument(program=0)  # 0はピアノを示すプログラム番号

    # ピアノをMIDIオブジェクトに追加
    midi.instruments.append(piano)


    # MIDIファイルの保存
    midi.write(file_name)

    return midi

def save_midi_file(file_name,notes,tempo):
    midi = create_midi_file(file_name,tempo)
    piano = midi.instruments[0]
    piano.notes = []
    for n in notes:
        note = pretty_midi.Note(velocity=100, pitch=n.pitch, start=n.start, end=n.end)
        piano.notes.append(note)

    midi.write(file_name)        

    return midi





class Note:
    def __init__(self, pitch, start, end):
        self.pitch = pitch
        self.start = start
        self.end = end

        self.active = False
        self.extend_left_active = False
        self.extend_right_active = False
        self.move_active = False
        self.delete = False

        self.a_pitch = pitch
        self.tmp_start = start
        self.tmp_end = end
        self.tmp_time = end-start
        self.tmp_x=0
        self.tmp_y=0

    #ノートデータを更新
    def updata(self):
        self.pitch = self.a_pitch
        self.start = self.tmp_start
        self.end = self.tmp_end
        self.active = False
        self.extend_left_active = False
        self.extend_right_active = False
        self.move_active = False


    #変更時間を計算
    def calculateChangeTime(self,unit_width,mouse_x,roll_x,sixteenth_note_duration,a=0):
        i = int(16*(self.tmp_x-roll_x-PIANO_WIDTH)/unit_width)+a
        x0 = roll_x + PIANO_WIDTH + i*unit_width//16
        x1 = x0 + unit_width//16
        w0 = self.tmp_x-x0
        w1 = x1-self.tmp_x
        if self.tmp_x-mouse_x>0:
            n = int(16*(mouse_x-self.tmp_x-w0)/unit_width)
            if self.tmp_x-mouse_x<w0:n=0
            change_time = n*sixteenth_note_duration
        else:
            n = int(16*(mouse_x-self.tmp_x-w1)/unit_width)+1
            if mouse_x-self.tmp_x<w1:n=0
            change_time = n*sixteenth_note_duration
        return change_time

    #左に伸ばす
    def extend_l(self,unit_width,mouse_x,roll_x,sixteenth_note_duration):
        change_time = self.calculateChangeTime(unit_width,mouse_x,roll_x,sixteenth_note_duration)
        self.tmp_start = self.start + change_time
        if self.tmp_start<0:
            self.tmp_start=0.0
            self.tmp_end=self.tmp_time

        if self.tmp_end-self.tmp_start<sixteenth_note_duration:
            self.tmp_start=self.tmp_end-sixteenth_note_duration


    #右に伸ばす
    def extend_r(self,unit_width,mouse_x,roll_x,sixteenth_note_duration):
        change_time = self.calculateChangeTime(unit_width,mouse_x,roll_x,sixteenth_note_duration,a=1)
        self.tmp_end = self.end + change_time

        if self.tmp_end-self.tmp_start<sixteenth_note_duration:
            self.tmp_end=self.tmp_start+sixteenth_note_duration

    #ノードを動かす
    def move(self,unit_width,x0,x1,mouse_x,mouse_y,roll_y,sixteenth_note_duration):
        self.a_pitch = int(HIGHEST_PITCH - (mouse_y-roll_y)/NOTE_HEIGHT)+1
        w0 = self.tmp_x-x0
        w1 = x1-self.tmp_x
        if self.tmp_x-mouse_x>0:
            n = int(16*(mouse_x-self.tmp_x-w0)/unit_width)
            if self.tmp_x-mouse_x<w0:n=0
            change_time = n*sixteenth_note_duration
        else:
            n = int(16*(mouse_x-self.tmp_x-w1)/unit_width)+1
            if mouse_x-self.tmp_x<w1:n=0
            change_time = n*sixteenth_note_duration
        self.tmp_start = self.start + change_time
        self.tmp_end = self.end + change_time
        if self.tmp_start<0:
            self.tmp_start=0.0
            self.tmp_end=self.tmp_time

    def handle_event(self, event, unit_width, roll_x, roll_y,sixteenth_note_duration,BEST_LENGTH_IN_SECONDS):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        x0 = (unit_width//4)*self.start/BEST_LENGTH_IN_SECONDS + roll_x + PIANO_WIDTH
        x1 = (unit_width//4)*self.end/BEST_LENGTH_IN_SECONDS + roll_x + PIANO_WIDTH
        w = x1-x0
        y0 = (HIGHEST_PITCH-self.a_pitch)*NOTE_HEIGHT + roll_y
        y1 = y0+NOTE_HEIGHT

        if event.type == pygame.MOUSEBUTTONDOWN:
            if (((x0 < mouse_x < x1) and (y0 < mouse_y < y1)) and not(self.active)):
                if event.button == 1: 
                    self.active = True
                    self.tmp_x,self.tmp_y = pygame.mouse.get_pos()

                elif event.button == 3:
                    self.delete = True
                
        elif event.type == pygame.MOUSEBUTTONUP:
            self.active = False
            self.updata()

        if self.active:
            if (mouse_x <= x0+w//5) and not(self.extend_right_active or self.move_active):
                self.extend_left_active = True
            elif (mouse_x >= x1-w//5) and not(self.extend_left_active or self.move_active):
                self.extend_right_active = True
            elif (x0+w//5<mouse_x<x1-w//5) and not(self.extend_right_active or self.extend_left_active):
                self.move_active = True
        

        if self.extend_left_active:
            self.tmp_time = self.tmp_end - self.tmp_start
            self.extend_l(unit_width,mouse_x,roll_x,sixteenth_note_duration)
        elif self.extend_right_active:
            self.tmp_time = self.tmp_end - self.tmp_start
            self.extend_r(unit_width,mouse_x,roll_x,sixteenth_note_duration)
        elif self.move_active:
            self.tmp_time = self.tmp_end - self.tmp_start
            self.move(unit_width,x0,x1,mouse_x,mouse_y,roll_y,sixteenth_note_duration)
        

    def draw_note(self,screen,unit_width, roll_x, roll_y,BEST_LENGTH_IN_SECONDS):
        x0 = (unit_width//4)*self.tmp_start/BEST_LENGTH_IN_SECONDS + roll_x + PIANO_WIDTH
        x1 = (unit_width//4)*self.tmp_end/BEST_LENGTH_IN_SECONDS + roll_x + PIANO_WIDTH
        w = x1-x0
        y = (HIGHEST_PITCH-self.a_pitch)*NOTE_HEIGHT + roll_y
        rect = pygame.Rect(x0,y,w,NOTE_HEIGHT)
        pygame.draw.rect(screen,NOTE_COLOR,rect)
        pygame.draw.rect(screen,BLACK,rect,width=1)
        if self.active:
            w_color = []
            for i in range(3):
                c= min(int(NOTE_COLOR[i]*3),255)
                w_color.append(c)
            pygame.draw.rect(screen,w_color,rect,width=2)


class Scrollbar_hor:
    def __init__(self,x,y,w,h,daw_w,roll_w,x0=0):
        self.scroll_dragging = None
        self.bar_rect = pygame.Rect(x,y,w,h)
        self.handle_rect = pygame.Rect(x+x0+2,y+2,MIN_SCROLLBAR_THUMB_SIZE,h-4)
        self.scroll_x = x0*(roll_w+PIANO_WIDTH+SCROLLBAR_THICKNESS-daw_w)/(w-MIN_SCROLLBAR_THUMB_SIZE)
        self.active = False

    def draw(self,screen):
        pygame.draw.rect(screen,SCROLLBAR_COLOR,self.bar_rect)
        pygame.draw.rect(screen,HANDLE_COLOR,self.handle_rect)
        w_color = [int(SCROLLBAR_COLOR[i]*0.6) for i in range(3)]
        pygame.draw.rect(screen,w_color,self.bar_rect,width=1)

    def handle_event(self,event,daw_w,roll_w):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.handle_rect.collidepoint(event.pos):
                self.active = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.active = False

        if self.active:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            self.handle_rect.x = mouse_x - self.handle_rect.w/2

            if self.handle_rect.x < self.bar_rect.x:
                self.handle_rect.x = self.bar_rect.x
            elif self.handle_rect.x > self.bar_rect.x + self.bar_rect.w - self.handle_rect.w:
                self.handle_rect.x = self.bar_rect.x + self.bar_rect.w - self.handle_rect.w
            
            self.scroll_x = (self.handle_rect.x-self.bar_rect.x)*(roll_w+PIANO_WIDTH+SCROLLBAR_THICKNESS-daw_w)/(self.bar_rect.w-self.handle_rect.w)

class Scrollbar_var:
    def __init__(self,x,y,w,h,daw_h,roll_h,y0=0):
        self.scroll_dragging = None
        self.bar_rect = pygame.Rect(x,y,w,h)
        self.handle_rect = pygame.Rect(x+2,y+y0+2,w-4,MIN_SCROLLBAR_THUMB_SIZE)
        self.scroll_y = y0*(roll_h+BAR_MEASURE_HEIGHT+SCROLLBAR_THICKNESS-daw_h)/(h-MIN_SCROLLBAR_THUMB_SIZE)
        self.active = False

    def draw(self,screen):
        pygame.draw.rect(screen,SCROLLBAR_COLOR,self.bar_rect)
        pygame.draw.rect(screen,HANDLE_COLOR,self.handle_rect)
        w_color = [int(SCROLLBAR_COLOR[i]*0.6) for i in range(3)]
        pygame.draw.rect(screen,w_color,self.bar_rect,width=1)

    def handle_event(self,event,daw_h,roll_h):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.handle_rect.collidepoint(event.pos):
                self.active = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.active = False

        if self.active:
            mouse_x, mouse_y = pygame.mouse.get_pos()
            self.handle_rect.y = mouse_y - self.handle_rect.h/2

            if self.handle_rect.y < self.bar_rect.y:
                self.handle_rect.y = self.bar_rect.y
            elif self.handle_rect.y > self.bar_rect.y + self.bar_rect.h - self.handle_rect.h:
                self.handle_rect.y = self.bar_rect.y + self.bar_rect.h - self.handle_rect.h

            self.scroll_y = (self.handle_rect.y-self.bar_rect.y)*(roll_h+BAR_MEASURE_HEIGHT+SCROLLBAR_THICKNESS-daw_h)/(self.bar_rect.h-self.handle_rect.h)


class Piano:
    def __init__(self,x,y):
        self.y = y
        self.rect = pygame.Rect(x,y,PIANO_WIDTH,NOTE_HEIGHT*((HIGHEST_PITCH-LOWEST_PITCH)))

    def draw_piano(self,screen):
        for i in range(int(7*(HIGHEST_PITCH-LOWEST_PITCH)/12+1)+5):
            w_rect = pygame.Rect(self.rect.x,self.rect.y+i*WHITE_KEY_HEIGHT-WHITE_KEY_HEIGHT//3,WHITE_KEY_WIDTH,WHITE_KEY_HEIGHT) 
            rect = pygame.Rect(self.rect.x+1,self.rect.y+i*WHITE_KEY_HEIGHT-WHITE_KEY_HEIGHT//3+1,WHITE_KEY_WIDTH-2,WHITE_KEY_HEIGHT-2)
            pygame.draw.rect(screen,BLACK,w_rect) 
            pygame.draw.rect(screen,WHITE,rect)
            if(i%7==0):
                string = "C" + str(int(7-i/7))
                text_screen = FONT.render(string, True, BLACK)
                screen.blit(text_screen, (self.rect.x+1+WHITE_KEY_WIDTH-FONTSIZE,self.rect.y+i*WHITE_KEY_HEIGHT-WHITE_KEY_HEIGHT//3+1+NOTE_HEIGHT/4))

        
        y=0
        for i in range(HIGHEST_PITCH-LOWEST_PITCH):
            pitch = HIGHEST_PITCH - i    
            if pitch%12 in BLACK_KEYS:
                rect = pygame.Rect(self.rect.x,self.rect.y+y,BLACK_KEY_WIDTH,KEY_HEIGHT[pitch%12]) 
                pygame.draw.rect(screen,BLACK,rect) 
            y+=KEY_HEIGHT[pitch%12]

    def updata(self,offset_y):
        self.rect.y = self.y -offset_y

        
class Pianoroll:
    def __init__(self,x,y,zoom_level):
        self.zoom_level = zoom_level
        self.unit_width = BASE_INTERVAL*zoom_level
        w = MAX_BAR*self.unit_width
        h = (HIGHEST_PITCH-LOWEST_PITCH+1)*NOTE_HEIGHT
        self.x = x
        self.y = y
        self.rect = pygame.Rect(x,y,w,h)
        self.notes = []
        
    def draw_grid_ver(self,screen):
        if self.zoom_level<4:a=1
        elif self.zoom_level<5:a=4
        elif self.zoom_level<9:a=8
        elif self.zoom_level<17:a=16
        else:a=16

        n = int(np.log2(a)-2)
        number_list = GRID_COLOR_NUMBER_LIST[n]
        for i in range(MAX_BAR*a):
            x = self.rect.x + PIANO_WIDTH + i*self.unit_width//a 
            color = GRID_COLOR[number_list[i%a]]
            pygame.draw.line(screen,color,(x,0),(x,self.rect.h))

    def draw_grid_hor(self,screen):
        for i in range(HIGHEST_PITCH-LOWEST_PITCH+2):
            y = self.rect.y + i*NOTE_HEIGHT 
            pygame.draw.line(screen,GRID_GRAY,(0,y),(self.rect.w,y))
    
    def draw_grid(self,screen):
        self.draw_grid_ver(screen)
        self.draw_grid_hor(screen)

    def draw_notes(self,screen,BEST_LENGTH_IN_SECONDS):
        roll_x = self.rect.x
        roll_y = self.rect.y
        for note in self.notes:
            note.draw_note(screen,self.unit_width, roll_x, roll_y,BEST_LENGTH_IN_SECONDS)

    def extract_notes_with_rests(self,midi_data):
        self.notes = []

        # 各インストゥルメントをループしてノート情報を取得する
        instrument = midi_data.instruments[0]  # 仮に最初のインストゥルメントを使用
        # ノートを開始時間でソート
        instrument.notes.sort(key=lambda note: note.start)
        
        # 各ノートと次のノートの間にある休符の検出
        for i in range(len(instrument.notes)):
            note = instrument.notes[i]
            self.notes.append(Note(note.pitch,note.start,note.end))

    def handle_event(self,event,sixteenth_note_duration,BEST_LENGTH_IN_SECONDS):
        for note in self.notes:
            note.handle_event(event,self.unit_width,self.rect.x,self.rect.y,sixteenth_note_duration,BEST_LENGTH_IN_SECONDS)
            if note.delete:
                i=self.notes.index(note)
                del self.notes[i]
        
    def updata(self,offset_x,offset_y,zoom_level):
        self.rect.x = self.x - offset_x
        self.rect.y = self.y - offset_y
        self.rect.w = MAX_BAR*BASE_INTERVAL*zoom_level
        self.zoom_level = zoom_level
        self.unit_width = BASE_INTERVAL*zoom_level

        
    def draw(self,screen,BEST_LENGTH_IN_SECONDS):
        pygame.draw.rect(screen,WHITE,self.rect)
        self.draw_grid(screen)
        self.draw_notes(screen,BEST_LENGTH_IN_SECONDS)

class BarMeasure:
    def __init__(self,daw_x,daw_y,daw_w,daw_h,w,h):
        self.x = daw_x+PIANO_WIDTH
        self.y = daw_y
        self.rect = pygame.Rect(daw_x+PIANO_WIDTH,daw_y,w,h)
        self.rect_blind1 = pygame.Rect(daw_x,daw_y,PIANO_WIDTH,BAR_MEASURE_HEIGHT)
        self.rect_blind2 = pygame.Rect(daw_x,daw_y+daw_h-SCROLLBAR_THICKNESS,PIANO_WIDTH,SCROLLBAR_THICKNESS)
        self.rect_blind3 = pygame.Rect(daw_x+daw_w-SCROLLBAR_THICKNESS,daw_y+daw_h-SCROLLBAR_THICKNESS,SCROLLBAR_THICKNESS,SCROLLBAR_THICKNESS)
        self.rect_blind4 = pygame.Rect(daw_x+daw_w-SCROLLBAR_THICKNESS,daw_y,SCROLLBAR_THICKNESS,BAR_MEASURE_HEIGHT)
        self.blinds = [self.rect_blind1,self.rect_blind2,self.rect_blind3,self.rect_blind4]

    def draw_grid_ver(self,screen,zoom_level):
        if zoom_level<4:a=1
        elif zoom_level<5:a=4
        elif zoom_level<9:a=8
        elif zoom_level<17:a=16
        else:a=16
        
        unit_width = zoom_level*BASE_INTERVAL
        n = int(np.log2(a)-2)
        number_list = GRID_COLOR_NUMBER_LIST[n]
        
        for i in range(MAX_BAR*a):
            string = ""
            x = self.rect.x + i*unit_width/a
            y = self.rect.y + self.rect.h*number_list[i%a]/10
            color = GRID_COLOR[number_list[i%a]]
            pygame.draw.line(screen,color,(x,y+self.rect.h/3),(x,self.rect.h))
            if a==1:
               string = str(i+1) 
            else:
               string = str(i//a+1)+"."+str(i%a+1) 


            text_screen = FONT.render(string, True, BLACK)
            screen.blit(text_screen, (x+2, self.rect.y+self.rect.h-2*FONTSIZE/3))

    def draw(self,screen,zoom_level):
        pygame.draw.rect(screen,BARMEASURE_COLOR,self.rect)
        pygame.draw.rect(screen,BLACK,self.rect,width=1)
        self.draw_grid_ver(screen,zoom_level)
        for blind in self.blinds:
            pygame.draw.rect(screen,BARMEASURE_BLIND_COLOR,blind)
            w_color = [int(BARMEASURE_BLIND_COLOR[i]*0.6) for i in range(3)]
            pygame.draw.rect(screen,w_color,blind,width=1)
            

    def updata(self,offset_x,zoom_level):
        self.rect.x = self.x - offset_x
        self.rect.w = MAX_BAR*zoom_level*BASE_INTERVAL

    

                    
class DAW:
    def __init__(self,midi_data,x,y,w,h,tempo):
        self.midi_file = 'output.mid'
        self.midi_data = midi_data
        self.now_key = 0
        self.now_mode = 0
        # テンポを取得（全てのテンポが同じであると仮定
        self.TEMPO = tempo
        # 1拍の長さを秒単位で計算
        self.BEST_LENGTH_IN_SECONDS = 60.0 / self.TEMPO
        self.sixteenth_note_duration = self.BEST_LENGTH_IN_SECONDS/4
        self.rect = pygame.Rect(x,y,w,h)
        self.zoom_level = INITIAL_ZOOM_LEVEL
        self.pianoroll = Pianoroll(x,BAR_MEASURE_HEIGHT,self.zoom_level)
        self.scr_hor = Scrollbar_hor(x+PIANO_WIDTH,y+h-SCROLLBAR_THICKNESS,w-PIANO_WIDTH-SCROLLBAR_THICKNESS,SCROLLBAR_THICKNESS,w,self.pianoroll.rect.w)
        self.scr_var = Scrollbar_var(x+w-SCROLLBAR_THICKNESS,y+BAR_MEASURE_HEIGHT,SCROLLBAR_THICKNESS,h-BAR_MEASURE_HEIGHT-SCROLLBAR_THICKNESS,h,self.pianoroll.rect.h,y0=INITIAL_Y)
        self.piano = Piano(x,y+BAR_MEASURE_HEIGHT)
        self.barmeasure = BarMeasure(x,y,w,h,BAR_MEASURE_WIDTH,BAR_MEASURE_HEIGHT)

        self.playing = False
        self.playhead_time = 0.0
        self.play_start_clock = 0.0
        self.play_thread = None
        self.start_time = 0

        try:
            outputs = mido.get_output_names()
            print("MIDI outputs:", outputs)

            self.midi_out = mido.open_output(outputs[0])
            print("MIDI出力ポートを開きました")
        except Exception as e:
            self.midi_out = None
            print("MIDI出力ポートが開けません:", e)

    def play_notes(self):
        self.playing = True
        self.playhead_time = 0.0
        self.play_start_clock = time.time()

        for note in self.pianoroll.notes:
            if not self.playing:
                break

            # ノート開始まで待つ
            while self.playing and self.playhead_time < note.start:
                self.playhead_time = time.time() - self.play_start_clock
                time.sleep(0.01)

            self.midi_out.send(mido.Message(
                'note_on',
                note=note.pitch,
                velocity=100
            ))

            while self.playing and self.playhead_time < note.end:
                self.playhead_time = time.time() - self.play_start_clock
                time.sleep(0.01)

            self.midi_out.send(mido.Message(
                'note_off',
                note=note.pitch,
                velocity=0
            ))

        self.playing = False


    def stop_notes(self):
        self.playing = False
        self.playhead_time = 0.0

        if self.midi_out is not None:
            for n in range(128):
                self.midi_out.send(mido.Message(
                    'note_off',
                    note=n,
                    velocity=0
                ))

    def draw_playhead(self, screen):

        x = (
            self.rect.x
            + PIANO_WIDTH
            + (self.pianoroll.unit_width // 4)
            * self.playhead_time
            / self.BEST_LENGTH_IN_SECONDS
            - self.scr_hor.scroll_x
        )

        pygame.draw.line(
            screen,
            (255, 0, 0),
            (int(x), self.rect.y),
            (int(x), self.rect.y + self.rect.h),
            2
        )

    def draw(self, screen):
        pygame.draw.rect(screen, WHITE, self.rect)
        self.pianoroll.draw(screen, self.BEST_LENGTH_IN_SECONDS)

        self.draw_playhead(screen)

        self.scr_hor.draw(screen)
        self.scr_var.draw(screen)
        self.piano.draw_piano(screen)
        self.barmeasure.draw(screen, self.zoom_level)

    def handle_event(self,event):
        mouse_x, mouse_y = pygame.mouse.get_pos()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_UP:
                self.zoom_level*=2
                if self.zoom_level>16:self.zoom_level=16
            elif event.key == pygame.K_DOWN:
                self.zoom_level/=2
                if self.zoom_level<1:self.zoom_level=1
            # Ctrl + Sの検出
            elif event.key == pygame.K_s and (pygame.key.get_mods() & pygame.KMOD_CTRL):
                print("Save")
                self.midi = save_midi_file(self.midi_file,self.pianoroll.notes,self.TEMPO)
            elif event.key == pygame.K_SPACE:
                if not self.playing:
                    self.play_thread = threading.Thread(
                        target=self.play_notes,
                        daemon=True
                    )
                    self.play_thread.start()
                    print("Play")
                else:
                    self.stop_notes()
                    print("Stop")


                    
                
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if ((self.rect.x+PIANO_WIDTH<mouse_x<self.rect.x+self.rect.w-SCROLLBAR_THICKNESS) and
            (self.rect.y+BAR_MEASURE_HEIGHT<mouse_y<self.rect.y+self.rect.h-SCROLLBAR_THICKNESS)):
                current_time = pygame.time.get_ticks()  # 現在の時間をミリ秒単位で取得
                
                if event.button == 1:  # 左クリック
                    global last_click_time
                    if current_time - last_click_time < double_click_time:
                        self.createNote(mouse_x,mouse_y)
                    last_click_time = current_time

        self.scr_hor.handle_event(event,self.rect.w,self.pianoroll.rect.w)
        self.scr_var.handle_event(event,self.rect.h,self.pianoroll.rect.h)
    
        if ((self.rect.x+PIANO_WIDTH<mouse_x<self.rect.x+self.rect.w-SCROLLBAR_THICKNESS) and
            (self.rect.y+BAR_MEASURE_HEIGHT<mouse_y<self.rect.y+self.rect.h-SCROLLBAR_THICKNESS)):
            if not(self.scr_hor.active or self.scr_var.active):
                self.pianoroll.handle_event(event,self.sixteenth_note_duration,self.BEST_LENGTH_IN_SECONDS)
            
    def createNote(self,mouse_x, mouse_y):
        if self.zoom_level<4:a=1
        elif self.zoom_level<5:a=4
        elif self.zoom_level<9:a=8
        elif self.zoom_level<17:a=16
        else:a=16

        x = mouse_x-self.pianoroll.rect.x-PIANO_WIDTH
        y = mouse_y-self.pianoroll.rect.y
        unit_w = self.zoom_level*BASE_INTERVAL//a
        note_pos = int(x/unit_w)
        note_picth = HIGHEST_PITCH-int(y/NOTE_HEIGHT)
        note_start = 16//a*self.sixteenth_note_duration*note_pos
        note_end = 16//a*self.sixteenth_note_duration*(note_pos+1)
        note = Note(note_picth,note_start,note_end)
        if self.check_same_note(note):self.pianoroll.notes.append(note)

    def updata(self):
        self.pianoroll.updata(self.scr_hor.scroll_x,self.scr_var.scroll_y,self.zoom_level)
        self.piano.updata(self.scr_var.scroll_y)
        self.barmeasure.updata(self.scr_hor.scroll_x,self.zoom_level)
        if self.playing:
            playhead_x = (
                PIANO_WIDTH
                + (self.pianoroll.unit_width // 4)
                * self.playhead_time
                / self.BEST_LENGTH_IN_SECONDS
            )

            center_x = self.rect.w * 0.5

            if playhead_x - self.scr_hor.scroll_x > center_x:
                self.scr_hor.scroll_x = playhead_x - center_x

    def tempo_change(self,tempo):
        self.TEMPO = tempo
        self.BEST_LENGTH_IN_SECONDS = 60.0 / self.TEMPO
        self.sixteenth_note_duration = self.BEST_LENGTH_IN_SECONDS/4

    def extract_notes_with_rests(self):
        self.pianoroll.extract_notes_with_rests(self.midi_data)

    def check_same_note(self,note):
        for n in self.pianoroll.notes:
            if (n.pitch == note.pitch and round(n.start,3) == round(note.start,3) and round(n.end,3) == round(note.end,3)):
                return False
        return True
            

# メインループ
def main():
    screen = pygame.display.set_mode(SCREEN_SIZE)
    midi_data = pretty_midi.PrettyMIDI(MIDI_FILE)
    daw = DAW(midi_data,0,0,SCREEN_WIDTH,SCREEN_HEIGHT,100)
    daw.extract_notes_with_rests()
    running = True

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
            daw.handle_event(event)
        daw.updata()

        daw.draw(screen)
        pygame.display.flip()

    pygame.quit()

if __name__ == '__main__':
    main()
