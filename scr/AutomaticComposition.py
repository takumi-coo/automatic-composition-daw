import os
import random
import sys
import time
import datetime

import pygame
import pygame.midi
import numpy as np

import melody
import DAW



pygame.init()
dt_now = datetime.datetime.now()
"""------定数------"""
model_path='new_note_prediction_model_64.h5'
SCR_WIDTH, SCR_HEIGHT = 650+1000, 700
BG_COLOR = (240, 240, 240)
FONT_COLOR = (0, 0, 0)
DROPDOWN_BG_COLOR = (200, 200, 200)
DROPDOWN_HOVER_COLOR = (150, 150, 150)
BUTTON_COLOR = (200, 200, 200)
ON_COLOR = (250,0,0)
OFF_COLOR = (150,150,150)
BUTTON_HOVER_COLOR = (150, 150, 150)
ACTIVE_COLOR = (100, 100, 100)
STEPPER_HOLD_DELAY = 0.5  # Delay before starting to repeat increment/decrement
STEPPER_HOLD_INTERVAL = 0.1  # Interval between repeated increment/decrement

GENERATER_X = 0
GENERATER_Y = 0
GENERATER_WIDTH = 650
GENERATER_HEIGHT = SCR_HEIGHT

FONTSIZE = 40
FONT = pygame.font.Font(None, FONTSIZE)

KEY_X = 50
KEY_Y = 50
KEY_WIDTH = 150
KEY_HEIGHT = FONTSIZE

SEED_X = 50
SEED_Y = 150
SEED_WIDTH = 150
SEED_HEIGHT = FONTSIZE

MODE_X = 50
MODE_Y = 250
MODE_WIDTH = 150
MODE_HEIGHT = FONTSIZE

TEMPO_X = 50
TEMPO_Y = 350
TEMPO_WIDTH = 150
TEMPO_HEIGHT = FONTSIZE
INITIAL_TEMPO = 120


MLE_BUTTON_CEN = (475,SEED_Y+FONTSIZE//2)
MLE_BUTTON_R = FONTSIZE//2

ARRANGE_BUTTON_X = 350
ARRANGE_BUTTON_Y = MODE_Y-5
ARRANGE_BUTTON_WIDTH = 200
ARRANGE_BUTTON_HEIGHT = FONTSIZE

GENERATE_BUTTON_X = 350
GENERATE_BUTTON_Y = TEMPO_Y-5
GENERATE_BUTTON_WIDTH = 200
GENERATE_BUTTON_HEIGHT = FONTSIZE


DAW_X = GENERATER_X+GENERATER_WIDTH
DAW_Y = 0
DAW_WIDTH = 1000
DAW_HEIGHT = SCR_HEIGHT

majScale = [0, 0, 0, 2, 4, 5, 7, 9, 11, 12, None, None]  # メジャースケール
minScale = [0, 0, 0, 2, 3, 5, 7, 8, 10, 12, None, None]  # マイナースケール
root_char = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
root_num = [60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71]  # 各Keyのルート音
mode_char = ["Major","Minor"]

seed_char = ["self","1/f"]

A4 = 69  # 基準音(A4)

"""----------------"""


def pseudoInversionMethod(beat_num):
    a = [0, 0, 0]
    t = beat_num % 8 + 1

    a[0] = random.randint(0, 2)
    if t % 2 == 0:
        a[1] = random.randint(0, 4)
    if t % 4 == 0:
        a[2] = random.randint(0, 8)

    a = np.array(a)

    return a.sum()


class Dropdown:
    def __init__(self, x, y, w, h, font, main, options):
        self.rect = pygame.Rect(x, y, w, h)
        self.color = DROPDOWN_BG_COLOR
        self.font = font
        self.main = main
        self.options = options
        self.active = False
        self.selected = None


    def draw_obj(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        text_screen = self.font.render(self.main, True, FONT_COLOR)
        l = len(self.main)
        screen.blit(text_screen, (self.rect.x + self.rect.w/2-FONTSIZE*l/4, self.rect.y + 10))
        
        if self.active:
            # Calculate dropdown height based on the number of options
            dropdown_height = len(self.options) * self.rect.height
            dropdown_rect = pygame.Rect(self.rect.x, self.rect.y + self.rect.height, self.rect.width, dropdown_height)
            pygame.draw.rect(screen, self.color, dropdown_rect)
            
            for i, option in enumerate(self.options):
                option_rect = pygame.Rect(self.rect.x, self.rect.y + (i + 1) * self.rect.height, self.rect.width, self.rect.height)
                pygame.draw.rect(screen, self.color if self.selected != i else DROPDOWN_HOVER_COLOR, option_rect)
                text_screen = self.font.render(option, True, FONT_COLOR)
                screen.blit(text_screen, (option_rect.x + 5, option_rect.y + 5))

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.active = not self.active
            elif self.active:
                for i, option_rect in enumerate(self.option_rects):
                    if option_rect.collidepoint(event.pos):
                        self.selected = i
                        self.main = self.options[i]
                        self.active = False
                        break
                else:
                    self.active = False


    def update(self):
        self.option_rects = []
        for i, option in enumerate(self.options):
            option_rect = pygame.Rect(self.rect.x, self.rect.y + (i + 1) * self.rect.height , self.rect.width, self.rect.height)
            self.option_rects.append(option_rect)

        self.operating = self.active

    def select_first_option(self):
        if self.options:
            self.selected = 0
            self.main = self.options[0]

class Stepper:
    def __init__(self, x, y, w, h, font,init_v, min_value=0, max_value=300, step=1):
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font
        self.value = init_v
        self.min_value = min_value
        self.max_value = max_value
        self.step = step

        self.button_up_rect = pygame.Rect(x + w - h, y, h, h // 2)
        self.button_down_rect = pygame.Rect(x + w - h, y + h // 2, h, h // 2)
        self.hovered_up = False
        self.hovered_down = False
        self.holding_up = False
        self.holding_down = False
        self.hold_start_time = 0
        self.last_hold_time = 0
        self.active = False
        self.input_value = ""


    def draw_obj(self, screen):
        # Change color if active
        color = ACTIVE_COLOR if self.active else BUTTON_COLOR

        pygame.draw.rect(screen, color, self.rect)
        display_value = self.input_value if self.active else str(self.value)
        value_screen = self.font.render(display_value, True, FONT_COLOR)
        screen.blit(value_screen, (self.rect.x + self.rect.w/2 - FONTSIZE*len(display_value)/3, self.rect.y + FONTSIZE/4))

        # Draw up button
        pygame.draw.rect(screen, BUTTON_HOVER_COLOR if self.hovered_up else BUTTON_COLOR, self.button_up_rect)
        pygame.draw.polygon(screen, FONT_COLOR, [(self.button_up_rect.centerx, self.button_up_rect.y + 5), 
                                                  (self.button_up_rect.x + 5, self.button_up_rect.bottom - 5), 
                                                  (self.button_up_rect.right - 5, self.button_up_rect.bottom - 5)])

        # Draw down button
        pygame.draw.rect(screen, BUTTON_HOVER_COLOR if self.hovered_down else BUTTON_COLOR, self.button_down_rect)
        pygame.draw.polygon(screen, FONT_COLOR, [(self.button_down_rect.centerx, self.button_down_rect.bottom - 5), 
                                                  (self.button_down_rect.x + 5, self.button_down_rect.y + 5), 
                                                  (self.button_down_rect.right - 5, self.button_down_rect.y + 5)])

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.button_up_rect.collidepoint(event.pos):
                self.value = min(self.value + self.step, self.max_value)
                self.holding_up = True
                self.hold_start_time = time.time()
            elif self.button_down_rect.collidepoint(event.pos):
                self.value = max(self.value - self.step, self.min_value)
                self.holding_down = True
                self.hold_start_time = time.time()
            elif self.rect.collidepoint(event.pos):
                self.active = True
                self.input_value = ""
            else:
                self.active = False
                self.input_value = ""
        elif event.type == pygame.MOUSEBUTTONUP:
            self.holding_up = False
            self.holding_down = False
        elif event.type == pygame.MOUSEMOTION:
            self.hovered_up = self.button_up_rect.collidepoint(event.pos)
            self.hovered_down = self.button_down_rect.collidepoint(event.pos)
        elif event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                if self.input_value.isdigit():
                    self.value = min(max(int(self.input_value), self.min_value), self.max_value)
                self.active = False
                self.input_value = ""
            elif event.key == pygame.K_BACKSPACE:
                self.input_value = self.input_value[:-1]
                if self.input_value.isdigit():
                    self.value = min(max(int(self.input_value), self.min_value), self.max_value)
            elif event.unicode.isdigit():
                self.input_value += event.unicode
                if self.input_value.isdigit():
                    self.value = min(max(int(self.input_value), self.min_value), self.max_value)

    def update(self):
        current_time = time.time()
        if self.holding_up:
            if current_time - self.hold_start_time > STEPPER_HOLD_DELAY:
                if current_time - self.last_hold_time > STEPPER_HOLD_INTERVAL:
                    self.value = min(self.value + self.step, self.max_value)
                    self.last_hold_time = current_time
        elif self.holding_down:
            if current_time - self.hold_start_time > STEPPER_HOLD_DELAY:
                if current_time - self.last_hold_time > STEPPER_HOLD_INTERVAL:
                    self.value = max(self.value - self.step, self.min_value)
                    self.last_hold_time = current_time

class Seed(Dropdown):
    def __init__(self, x, y, w, h, font, text_width, main, options):
        super().__init__(x+text_width, y-5, w, h, font, main, options)
        self.width = 5
        self.text_width = text_width
        self.bg = pygame.Rect(x-self.width,y-self.width-5,w+2*self.width+text_width,h+2*self.width)

    def draw(self,screen):
        a = 1-0.3/ self.width
        bg_color = (DROPDOWN_BG_COLOR[0] * a, DROPDOWN_BG_COLOR[1] * a, DROPDOWN_BG_COLOR[2] * a)

        pygame.draw.rect(screen,bg_color,self.bg)
        for i in range(1,self.width):
            a = 1-0.3*((i + 1) / self.width) 
            bg_color = (DROPDOWN_BG_COLOR[0] * a, DROPDOWN_BG_COLOR[1] * a, DROPDOWN_BG_COLOR[2] * a)
            x=self.bg.x+i+self.text_width
            y=self.bg.y+i
            w=self.bg.w-2*i-self.text_width
            h=self.bg.h-2*i
            bg=pygame.Rect(x,y,w,h)
            pygame.draw.rect(screen,bg_color,bg)

        text_screen = self.font.render("Seed", True, FONT_COLOR)
        screen.blit(text_screen, (self.bg.x+self.width*2, self.bg.y+self.width+5))
        self.draw_obj(screen)


class Key(Dropdown):
    def __init__(self, x, y, w, h, font, text_width, main, options):
        super().__init__(x+text_width, y-5, w, h, font, main, options)
        self.width = 5
        self.text_width = text_width
        self.bg = pygame.Rect(x-self.width,y-self.width-5,w+2*self.width+text_width,h+2*self.width)

    def draw(self,screen):
        a = 1-0.3/ self.width
        bg_color = (DROPDOWN_BG_COLOR[0] * a, DROPDOWN_BG_COLOR[1] * a, DROPDOWN_BG_COLOR[2] * a)

        pygame.draw.rect(screen,bg_color,self.bg)
        for i in range(1,self.width):
            a = 1-0.3*((i + 1) / self.width) 
            bg_color = (DROPDOWN_BG_COLOR[0] * a, DROPDOWN_BG_COLOR[1] * a, DROPDOWN_BG_COLOR[2] * a)
            x=self.bg.x+i+self.text_width
            y=self.bg.y+i
            w=self.bg.w-2*i-self.text_width
            h=self.bg.h-2*i
            bg=pygame.Rect(x,y,w,h)
            pygame.draw.rect(screen,bg_color,bg)

        text_screen = self.font.render("Key", True, FONT_COLOR)
        screen.blit(text_screen, (self.bg.x+self.width*2, self.bg.y+self.width+5))
        self.draw_obj(screen)

class Tempo(Stepper):
    def __init__(self, x, y, w, h, font, text_width,init_v, min_value=0, max_value=300, step=1):
        super().__init__(x+text_width, y-5, w, h, font,init_v, min_value, max_value, step)
        self.width = 5
        self.text_width = text_width
        self.bg = pygame.Rect(x-self.width,y-self.width-5,w+2*self.width+text_width,h+2*self.width)
        
    def draw(self,screen):
        a = 1-0.3/ self.width
        bg_color = (DROPDOWN_BG_COLOR[0] * a, DROPDOWN_BG_COLOR[1] * a, DROPDOWN_BG_COLOR[2] * a)

        pygame.draw.rect(screen,bg_color,self.bg)
        for i in range(1,self.width):
            a = 1-0.3*((i + 1) / self.width) 
            bg_color = (DROPDOWN_BG_COLOR[0] * a, DROPDOWN_BG_COLOR[1] * a, DROPDOWN_BG_COLOR[2] * a)
            x=self.bg.x+i+self.text_width
            y=self.bg.y+i
            w=self.bg.w-2*i-self.text_width
            h=self.bg.h-2*i
            bg=pygame.Rect(x,y,w,h)
            pygame.draw.rect(screen,bg_color,bg)

        text_screen = self.font.render("Tempo", True, FONT_COLOR)
        screen.blit(text_screen, (self.bg.x+self.width*2, self.bg.y+self.width+5))
        self.draw_obj(screen)


class Mode(Dropdown):
    def __init__(self, x, y, w, h, font, text_width, main, options):
        super().__init__(x+text_width, y-5, w, h, font, main, options)
        self.width = 5
        self.text_width = text_width
        self.bg = pygame.Rect(x-self.width,y-self.width-5,w+2*self.width+text_width,h+2*self.width)

    def draw(self,screen):
        a = 1-0.3/ self.width
        bg_color = (DROPDOWN_BG_COLOR[0] * a, DROPDOWN_BG_COLOR[1] * a, DROPDOWN_BG_COLOR[2] * a)

        pygame.draw.rect(screen,bg_color,self.bg)
        for i in range(1,self.width):
            a = 1-0.3*((i + 1) / self.width) 
            bg_color = (DROPDOWN_BG_COLOR[0] * a, DROPDOWN_BG_COLOR[1] * a, DROPDOWN_BG_COLOR[2] * a)
            x=self.bg.x+i+self.text_width
            y=self.bg.y+i
            w=self.bg.w-2*i-self.text_width
            h=self.bg.h-2*i
            bg=pygame.Rect(x,y,w,h)
            pygame.draw.rect(screen,bg_color,bg)

        text_screen = self.font.render("Mode", True, FONT_COLOR)
        screen.blit(text_screen, (self.bg.x+self.width*2, self.bg.y+self.width+5))
        self.draw_obj(screen)

class Button:
    def __init__(self,x,y,w,h,width,text,font,color,pushcolor):
        self.rect = pygame.Rect(x,y,w,h)
        self.width = width
        self.text = text
        self.font = font
        self.color = color
        self.pushcolor = pushcolor
        self.bg = pygame.Rect(x-width,y-width,w+2*width,h+2*width)
        self.push = False

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.push = True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.push = False

    def updade(self):
        pass

    def draw(self, screen):
        a = 1-0.3/ self.width
        bg_color = (DROPDOWN_BG_COLOR[0] * a, DROPDOWN_BG_COLOR[1] * a, DROPDOWN_BG_COLOR[2] * a)
        pygame.draw.rect(screen,bg_color,self.bg)
        for i in range(1,self.width):
            a = 1-0.3*((i + 1) / self.width) 
            bg_color = (DROPDOWN_BG_COLOR[0] * a, DROPDOWN_BG_COLOR[1] * a, DROPDOWN_BG_COLOR[2] * a)
            x=self.bg.x+i
            y=self.bg.y+i
            w=self.bg.w-2*i
            h=self.bg.h-2*i
            bg=pygame.Rect(x,y,w,h)
            pygame.draw.rect(screen,bg_color,bg)
        color = self.color if self.push else self.pushcolor
        pygame.draw.rect(screen,color,self.rect)
        text_screen = self.font.render(self.text, True, FONT_COLOR)
        screen.blit(text_screen, (self.rect.x+self.width*2, self.rect.y+self.width+5))
    
class CircularButtonSwitch:
    def __init__(self,center, radius, name , font):
        self.center = center
        self.radius = radius
        self.name = name
        self.button_color = OFF_COLOR  
        self.button_on = False
        self.font = font

    def draw(self,screen):
        # ボタン描画
        pygame.draw.circle(screen, self.button_color, self.center, self.radius)

        # スイッチの名前を表示
        label = self.font.render(self.name, True, (0, 0, 0))  # BLACK
        label_rect = label.get_rect(center=(self.center[0] - self.radius - 60, self.center[1]))
        screen.blit(label, label_rect)

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            # ボタンの円形領域内にクリックがあるかどうかを判定
            if (mouse_pos[0] - self.center[0])**2 + (mouse_pos[1] - self.center[1])**2 <= self.radius**2:
                self.button_on = not self.button_on
                self.button_color = ON_COLOR if self.button_on else OFF_COLOR  # GREEN or RED

class ObjManager:
    def __init__(self):
        self.objects=[]

    def setObj(self,obj):
        if type(obj)==type([]):
            self.objects=self.objects+obj
        else:
            self.objects.append(obj)

    def changeOrder(self):
        for i,obj in enumerate(self.objects):
            if obj.active:
                self.objects.pop(i)
                self.objects.append(obj)
                break

    def update(self):
        for obj in self.objects:
            obj.update()

    def draw(self,screen):
        for obj in self.objects:
            obj.draw(screen)

class Generater:
    def __init__(self,x,y,w,h):
        self.rect = pygame.Rect(x,y,w,h)
        self.key = Key(KEY_X, KEY_Y, KEY_WIDTH, KEY_HEIGHT, FONT, 2.5*KEY_HEIGHT, root_char[0], root_char)
        self.key.select_first_option()
        self.seed = Seed(SEED_X, SEED_Y, SEED_WIDTH, SEED_HEIGHT, FONT, 2.5*SEED_HEIGHT, seed_char[0], seed_char)
        self.seed.select_first_option()
        self.mode = Mode(MODE_X, MODE_Y, MODE_WIDTH, MODE_HEIGHT, FONT, 2.5*MODE_HEIGHT, mode_char[0], mode_char)
        self.mode.select_first_option()
        self.tempostepper = Tempo(TEMPO_X , TEMPO_Y, TEMPO_WIDTH, TEMPO_HEIGHT, FONT, 2.5*TEMPO_HEIGHT, INITIAL_TEMPO, min_value=0, max_value=300, step=1)
        self.objmanager=ObjManager()
        self.objmanager.setObj([self.key,self.mode,self.tempostepper,self.seed])


        self.mlebutton = CircularButtonSwitch(MLE_BUTTON_CEN, MLE_BUTTON_R,"MLE",FONT)
        self.arrangebutton = Button(ARRANGE_BUTTON_X,ARRANGE_BUTTON_Y,ARRANGE_BUTTON_WIDTH,ARRANGE_BUTTON_HEIGHT,5,"Arrange",FONT,BUTTON_HOVER_COLOR,BUTTON_COLOR)
        self.generatebutton = Button(GENERATE_BUTTON_X,GENERATE_BUTTON_Y,GENERATE_BUTTON_WIDTH,GENERATE_BUTTON_HEIGHT,5,"Generate",FONT,BUTTON_HOVER_COLOR,BUTTON_COLOR)
        

    def handle_event(self,event):
        if(not self.key.active):self.tempostepper.handle_event(event)
        self.key.handle_event(event)
        self.seed.handle_event(event)
        self.mode.handle_event(event)
        self.mlebutton.handle_event(event)
        self.arrangebutton.handle_event(event)
        self.generatebutton.handle_event(event)

    def updata(self):
        self.objmanager.update()
        self.objmanager.changeOrder()

    def draw(self,screen):
        a=25
        pygame.draw.rect(screen,DAW.BARMEASURE_BLIND_COLOR,self.rect)
        rect = pygame.Rect(self.rect.x+a,self.rect.y+a,self.rect.w-2*a,self.rect.h-2*a)
        pygame.draw.rect(screen,DAW.BARMEASURE_COLOR,rect)
        self.mlebutton.draw(screen)
        self.generatebutton.draw(screen)
        self.arrangebutton.draw(screen)
        self.objmanager.draw(screen)
    


def main():
    pygame.mixer.init()
    screen = pygame.display.set_mode((SCR_WIDTH, SCR_HEIGHT))
    pygame.display.set_caption("Automatic Composition")

    seed_file = 'seed.mid'
    path = os.path.normpath(seed_file) 
    midi_data = DAW.create_midi_file(path,INITIAL_TEMPO)

    running = True
    generater = Generater(GENERATER_X,GENERATER_Y,GENERATER_WIDTH,GENERATER_HEIGHT)
    
    daw = DAW.DAW(midi_data,DAW_X,DAW_Y,DAW_WIDTH,DAW_HEIGHT,INITIAL_TEMPO)
    daw.pianoroll.extract_notes_with_rests(midi_data)
    
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
            generater.handle_event(event)
            daw.handle_event(event)
        
        generater.updata()
        daw.updata()

        screen.fill(BG_COLOR)

        daw.draw(screen)
        generater.draw(screen)
        
        pygame.display.flip()

        if generater.generatebutton.push:
            daw.pianoroll.notes = melody.generate_melody(model_path,daw.pianoroll.notes,generater.key.selected,daw.now_key,generater.mode.selected,daw.now_mode,tempo=generater.tempostepper.value,now_tempo=daw.TEMPO,seed=generater.seed.selected,mle=generater.mlebutton.button_on)
            print("Generate success")
            daw.now_mode = generater.mode.selected
            daw.now_key = generater.key.selected
            daw.tempo_change(generater.tempostepper.value)
            generater.generatebutton.push = False
        elif generater.arrangebutton.push:
            daw.pianoroll.notes = melody.arrange_melodey(daw.pianoroll.notes,generater.key.selected,daw.now_key,generater.mode.selected,generater.tempostepper.value,daw.TEMPO)
            print("Arrange success")
            daw.now_key = generater.key.selected
            daw.now_mode = generater.mode.selected
            daw.tempo_change(generater.tempostepper.value)
            generater.arrangebutton.push = False


        pygame.midi.init()


    date = "_"+str(dt_now.month)+"_"+str(dt_now.day)+"_"+str(dt_now.hour)+"_"+str(dt_now.minute)+"_"+str(dt_now.second)+".mid"
    output_file = 'output'+ date
    DAW.save_midi_file(output_file,daw.pianoroll.notes,daw.TEMPO)

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()