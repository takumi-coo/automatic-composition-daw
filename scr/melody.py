import pretty_midi
import os
import numpy as np
import tensorflow as tf
import random
import DAW

seq_length=64
limBEAT_LENGTH=4
C4=60
N=100
KEY_LENGTH=89
NOTE_LENGTH=64
eps = 0.01
np.set_printoptions(precision=3)


def note_class(data,sixteenth_note_seconds):
    notes=[]
    note_end=0
    for d in data:
        note_start = note_end
        note_end = note_start + sixteenth_note_seconds*(d[1]+1)
        if d[0]>0:
            note_pitch = d[0]
            notes.append(DAW.Note(note_pitch,note_start,note_end))

    return notes
            

def pseudoInversionMethod(beat_num,a):
    t = beat_num % 8 + 1

    a[0] = random.randint(0, 1)
    if t % 2 == 0:
        a[1] = random.randint(0, 3)
    if t % 4 == 0:
        a[2] = random.randint(0, 7)

    a = np.array(a)

    return a,a.sum()

def read_file_to_array(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        lines = file.readlines()

    notes=[]
    lines_array = [line.strip() for line in lines]
    for data in lines_array:
        i=0
        while data[i]!=" ":
            i+=1
        note = [int(data[:i]),float(data[i+1:])]
        notes.append(note)

    return notes

#八分音符を生成
def make_data(n,tempo):
    datalist=[]
    a=[0,0,0]
    for i in range(n):
        a,t = pseudoInversionMethod(i,a)
        majScale = [0, 0 ,0, 2, 4 ,5, 7, 9, 11, 12, None, None]

        if majScale[t] is None:
            pitch=-1
        else:
            pitch=majScale[t]+C4
        
        for j in range(2):
            datalist.append([pitch,1,tempo])

    return np.array(datalist)


def change_form(data):
    datalist=[]
    for note in data:
        length = int(note[1]/0.25)
        for i in range(length):
            datalist.append([note[0],length-1])

    return datalist


def extract_notes_with_rests(midi_data):
    notes_info = []
    
    # テンポを取得（全てのテンポが同じであると仮定）
    tempo = midi_data.get_tempo_changes()[1][0]
    
    # 1拍の長さを秒単位で計算
    beat_length_in_seconds = 60.0 / tempo
    
    # 各インストゥルメントをループしてノート情報を取得する
    instrument = midi_data.instruments[0]  # 仮に最初のインストゥルメントを使用
    # ノートを開始時間でソート
    instrument.notes.sort(key=lambda note: note.start)
    
    # ノートの開始位置を初期化
    previous_note_end = 0

    # 最初のノート前の休符をチェック
    if instrument.notes[0].start > 0:
        rest_length_in_seconds = instrument.notes[0].start
        rest_length_in_beats = rest_length_in_seconds / beat_length_in_seconds
        num_sixteenth_notes = int(rest_length_in_beats / 0.25)
        if num_sixteenth_notes < 16:
            for j in range(num_sixteenth_notes):
                if j == 0 and num_sixteenth_notes == 1:
                    notes_info.append([-1, 0])
                else:
                    notes_info.append([-1, num_sixteenth_notes-1])

    # 各ノートと次のノートの間にある休符の検出
    for i in range(len(instrument.notes)):
        note = instrument.notes[i]
        note_number = note.pitch
        note_length_in_seconds = note.end - note.start
        note_length_in_beats = note_length_in_seconds / beat_length_in_seconds
        num_sixteenth_notes = int(note_length_in_beats / 0.25)
        
        for j in range(num_sixteenth_notes):
            if j == 0 and num_sixteenth_notes == 1:
                notes_info.append([note_number, 0])
            else:
                notes_info.append([note_number, num_sixteenth_notes-1])
        
        previous_note_end = note.end
        
        # 次のノートまでの休符を計算
        if i < len(instrument.notes) - 1:
            next_note_start = instrument.notes[i + 1].start
            rest_length_in_seconds = next_note_start - previous_note_end
            if rest_length_in_seconds > 0:
                rest_length_in_beats = rest_length_in_seconds / beat_length_in_seconds
                num_sixteenth_notes = int(rest_length_in_beats / 0.25)
                for j in range(num_sixteenth_notes):
                    if j == 0 and num_sixteenth_notes == 1:
                        notes_info.append([-1, 0])
                    else:
                        notes_info.append([-1, num_sixteenth_notes-1])

    return notes_info

def notes_sort(notes):
    n = len(notes)
    for i in range(n):
        # Last i elements are already in place
        for j in range(0, n - i - 1):
            # Traverse the array from 0 to n - i - 1
            # Swap if the element found is greater than the next element
            if notes[j].start > notes[j + 1].start:
                notes[j], notes[j + 1] = notes[j + 1], notes[j]

    return notes

def create_data_from_notes(notes, tempo, now_tempo):
    notes_info = []

    beat_length_in_seconds = 60.0 / tempo

    now_sixteenth_note_duration = 60.0 /now_tempo/4
    sixteenth_note_duration = beat_length_in_seconds/4
    end_time = 0.0
    for note in notes:
        value = (note.end-note.start)/now_sixteenth_note_duration
        note.start = end_time
        note.end = note.start + value*sixteenth_note_duration
        end_time = note.end

    # ノートを開始時間でソート
    notes = notes_sort(notes)
    
    # ノートの開始位置を初期化
    previous_note_end = 0

    # 最初のノート前の休符をチェック
    if notes[0].start > 0:
        rest_length_in_seconds = notes[0].start
        rest_length_in_beats = rest_length_in_seconds / beat_length_in_seconds
        num_sixteenth_notes = int(rest_length_in_beats / 0.25)
        if num_sixteenth_notes < 16:
            for j in range(num_sixteenth_notes):
                if j == 0 and num_sixteenth_notes == 1:
                    notes_info.append([-1, 0, tempo])
                else:
                    notes_info.append([-1, num_sixteenth_notes-1, tempo])

                  

    # 各ノートと次のノートの間にある休符の検出
    for i in range(len(notes)):
        note = notes[i]
        note_number = note.pitch
        note_length_in_seconds = note.end - note.start
        note_length_in_beats = note_length_in_seconds / beat_length_in_seconds
        num_sixteenth_notes = int(round(note_length_in_beats / 0.25,0))

        
        for j in range(num_sixteenth_notes):
            if j == 0 and num_sixteenth_notes == 1:
                notes_info.append([note_number, 0])
            else:
                notes_info.append([note_number, num_sixteenth_notes-1, tempo])
        
        previous_note_end = note.end
        
        # 次のノートまでの休符を計算
        if i < len(notes) - 1:
            next_note_start = notes[i + 1].start
            rest_length_in_seconds = next_note_start - previous_note_end
            if rest_length_in_seconds > 0:
                rest_length_in_beats = rest_length_in_seconds / beat_length_in_seconds
                num_sixteenth_notes = int(rest_length_in_beats / 0.25)
                for j in range(num_sixteenth_notes):
                    if j == 0 and num_sixteenth_notes == 1:
                        notes_info.append([-1, 0, tempo])
                    else:
                        notes_info.append([-1, num_sixteenth_notes-1, tempo])

    return notes_info


def create_midi_from_data(data, tempo):
    """
    フォーマットされたノートデータからMIDIファイルを作成します。
    
    Parameters:
    - data: ノートのリスト、形式は [note_number, note_velocity, note_length_in_beats, note_position]
    - tempo: MIDIファイルのテンポ（デフォルトは120 BPM）
    
    Returns:
    - MIDIファイルを表すPrettyMIDIオブジェクト
    """
    midi_data = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    piano_program = pretty_midi.instrument_name_to_program('Acoustic Grand Piano')
    piano = pretty_midi.Instrument(program=piano_program)
    
    # データからノートを作成
    pre_length=0

    for note_info in data:
        note_length = 0.25*(note_info[1]+1)# ノートの長さを秒に変換
        if(note_info[0]>0):
            note_number = note_info[0] 
            note_velocity = 100  
            note_start = pre_length*(60.0 / tempo)  # ノートの開始位置を秒に変換
            note_end = note_start + note_length* (60.0 / tempo)
            # ノートを作成して楽器に追加
            note = pretty_midi.Note(velocity=note_velocity, pitch=note_number, start=note_start, end=note_end)
            piano.notes.append(note)
        pre_length+=note_length

        
    # 楽器をMIDIデータに追加
    midi_data.instruments.append(piano)
    
    return midi_data

def connect_note(data):

    i=0
    while i<data.shape[0]:
        n=data[i][1]+1
        data = np.delete(data,slice(i+1,i+n),0)
        i+=1

    return data


def change_key(data,key):
    key=key%12
    if key>6:
        key-=12
    for note in data:
        if note[0]>0:
            note[0]+=key

    return data

def change_mode(data,mode,now_key):
    if mode>0:
        for note in data:
            if note[0]%12==(4+now_key)%12 or note[0]%12==(9+now_key)%12 or note[0]%12==(11+now_key)%12:
                note[0]-=1
    elif mode==0:
        for note in data:
            if note[0]%12==(3+now_key)%12 or note[0]%12==(8+now_key)%12 or note[0]%12==(10+now_key)%12:
                note[0]+=1

    return data
            
def arrange_melodey(notes,key=0,now_key=0,mode=0,tempo= 120, now_tempo=120):
    sixteenth_note_seconds = 60.0/tempo/4
    data = create_data_from_notes(notes,tempo,now_tempo)
    data = connect_note(np.array(data))
    data = change_mode(data,mode,now_key)
    key = key - now_key
    data = change_key(data,key)
    data = list(data)
    notes = note_class(data,sixteenth_note_seconds)

    return notes


def generate_melody(model_path,notes=None,key=0,now_key=0,mode=0,now_mode=0,n = 50,HIGHEST_NOTE = 127,LOWEST_NOTE= 0,tempo= 120, now_tempo=120, seed=0, mle=False):
    sixteenth_note_seconds = 60.0/tempo/4
    # モデルの読み込み
    model = tf.keras.models.load_model(model_path)

    # ランダムな入力データの作成（ダミーの入力）
    major_scale_offsets = [0, 2, 4, 5, 7, 9, 11]
    NOTE_NUM_LIST = list(range(KEY_LENGTH))
    NOTE_NUM_LIST[-1]=-1
    NOTE_LENGTH_LIST = list(range(NOTE_LENGTH))

    if seed>0:
        data=make_data(seq_length//2,tempo).tolist()#疑似1/f乱数で生成
    else:
        if notes is not None and len(notes) > 0:
            data = create_data_from_notes(notes, tempo, now_tempo)
        else:
            data = make_data(seq_length // 2, tempo).tolist()#疑似1/f乱数で生成

        if now_key != 0:
            data = change_key(data,-now_key)

        if now_mode != 0:
            data = change_mode(data,0,0)

        #data=change_form(data)
        if len(data)<seq_length:
            n=seq_length-len(data)
            ex_data=make_data(n//2+1,tempo)
            data.extend(ex_data)


    # モデルの予測を繰り返し実行
    for i in range(n):
        # 入力データをバッチとして準備（次元を追加してバッチサイズ1のシーケンスとして扱う）
        input_data = np.expand_dims(data[-seq_length:], axis=0)
        
        # モデルによる予測を行う
        all_p = model.predict(input_data)
        pianoroll_p = all_p[0][:KEY_LENGTH]
        length_p = all_p[0][KEY_LENGTH:]

        for i,p in enumerate(pianoroll_p):
            if p<eps:pianoroll_p[i]=0
            else:pianoroll_p[i]=round(pianoroll_p[i],2)

        for i,p in enumerate(length_p):
            if p<eps:length_p[i]=0
            else:length_p[i]=round(length_p[i],2)

        if not mle:    
            sum_p = np.sum(pianoroll_p)
            if sum_p != 0:pianoroll_p = pianoroll_p / sum_p
            note_num = np.random.choice(a=NOTE_NUM_LIST,p=pianoroll_p)

            sum_p = np.sum(length_p)
            if sum_p != 0:length_p = length_p / sum_p
            note_length = np.random.choice(a=NOTE_LENGTH_LIST,p=length_p)

        else:
            max_pitch_p = np.amax(pianoroll_p)
            max_length_p = np.amax(length_p)
            pianoroll_p = list(pianoroll_p)
            length_p = list(length_p)

            note_num = pianoroll_p.index(max_pitch_p)
            note_length = length_p.index(max_length_p)

        note=[note_num,note_length,tempo]

        for i in range(note_length+1):
            data = np.vstack([data, note])

    for note in data:

        in_scale = False
        for ofset in major_scale_offsets:
            if note[0]%12==ofset or note[0]==-1:
                in_scale=True
                break

        if not(in_scale):
            note[0]+=1
        
        if not (LOWEST_NOTE <= note[0] <= HIGHEST_NOTE):
            note[0] = -1

    data = connect_note(data)
    data = change_mode(data,mode,0)
    data = change_key(data,key)
    notes = note_class(data,sixteenth_note_seconds)

    return notes




