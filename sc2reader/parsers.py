from itertools import chain

from sc2reader.objects import *
from sc2reader.utils import BIG_ENDIAN,LITTLE_ENDIAN

class SetupParser(object):
    def parse_join_event(self, buffer, frames, type, code, pid):
        return PlayerJoinEvent(frames, pid, type, code)
        
    def parse_start_event(self, buffer, frames, type, code, pid):
        return GameStartEvent(frames, pid, type, code)
        
class ActionParser(object):
    def parse_leave_event(self, buffer, frames, type, code, pid):
        return PlayerLeaveEvent(frames, pid, type, code)
    
    def parse_ability_event(self, buffer, frames, type, code, pid):
        """ Unit ability"""
        flag = buffer.read_byte()
        atype = buffer.read_byte()
        
        ability = None
        if atype & 0x20: # command card
            ability = buffer.read_byte() << 8 | buffer.read_byte() 
            if flag in (0x29, 0x19): # cancels
                # creation autoid number / object id
                ability = ability << 8 | buffer.read_byte()
                created_id = buffer.read_object_id() 
                # TODO : expose the id
                return AbilityEvent(frames, pid, type, code, ability)
                
            else:
                ability_flags = buffer.shift(6)
                ability = ability << 8 | ability_flags
              
                if ability_flags & 0x10:
                    # ability(3), coordinates (4), ?? (4)
                    location = buffer.read_coordinate()
                    buffer.skip(4)
                    return LocationAbilityEvent(frames, pid, type, code, ability, location)
                    
                elif ability_flags & 0x20:
                    # ability(3), object id (4),  object type (2), ?? (10)
                    code = buffer.read_short() # code??
                    obj_id = buffer.read_object_id()
                    obj_type = buffer.read_object_type()
                    target = (obj_id, obj_type,)
                    buffer.skip(10)
                    return TargetAbilityEvent(frames, pid, type, code, ability, target)
                    
                elif ability_flags & 0x30 == 0x00:
                    return AbilityEvent(frames, pid, type, code, ability)

        elif atype & 0x40: # location/move
            # coordinates (4), ?? (6)
            location = buffer.read_coordinate()
            buffer.skip(5)
            return LocationAbilityEvent(frames, pid, type, code, ability, location)
            
        elif atype & 0x80: # right-click on target?
            # ability (2), object id (4), object type (2), ?? (10)
            ability = buffer.read_byte() << 8 | buffer.read_byte() 
            obj_id = buffer.read_object_id()
            obj_type = buffer.read_object_type()
            target = (obj_id, obj_type,)
            buffer.skip(10)
            return TargetAbilityEvent(frames, pid, type, code, ability, target)
        
    def parse_selection_event(self, buffer, frames, type, code, pid):
        bank = code >> 4
        first = buffer.read_byte() # TODO ?

        deselect_flag = buffer.shift(2)
        if deselect_flag == 0x01: # deselect deselect mask
            mask = buffer.read_bitmask()
            deselect = lambda a: Selection.mask(a, mask)
        elif deselect_flag == 0x02: # deselect mask
            indexes = [buffer.read_byte() for i in range(buffer.read_byte())]
            deselect = lambda a: Selection.deselect(a, indexes)
        elif deselect_flag == 0x03: # replace mask
            indexes = [buffer.read_byte() for i in range(buffer.read_byte())]
            deselect = lambda a: Selection.replace(a, indexes)
        else:
            deselect = None
            
        # <count> (<type_id>, <count>,)*
        object_types = [ (buffer.read_object_type(read_modifier=True), buffer.read_byte(), ) for i in range(buffer.read_byte()) ]
        # <count> (<object_id>,)*
        object_ids = [ buffer.read_object_id() for i in range(buffer.read_byte()) ]

        # repeat types count times
        object_types = chain(*[[object_type,]*count for (object_type, count) in object_types])
        objects = zip(object_ids, object_types)

        return SelectionEvent(frames, pid, type, code, bank, objects, deselect)
        
    def parse_hotkey_event(self, buffer, frames, type, code, pid):
        hotkey = code >> 4
        action, mode = buffer.shift(2), buffer.shift(2)
        
        if mode == 1: # deselect overlay mask
            mask = buffer.read_bitmask()
            overlay = lambda a: Selection.mask(a, mask)
        elif mode == 2: # deselect mask
            indexes = [buffer.read_byte() for i in range(buffer.read_byte())]
            overlay = lambda a: Selection.deselect(a, indexes)
        elif mode == 3: # replace mask
            indexes = [buffer.read_byte() for i in range(buffer.read_byte())]
            overlay = lambda a: Selection.replace(a, indexes)
        else:
            overlay = None
            
        if action == 0:
            return SetToHotkeyEvent(frames, pid, type, code, hotkey, overlay)
        elif action == 1:
            return AddToHotkeyEvent(frames, pid, type, code, hotkey, overlay)
        elif action == 2:
            return GetHotkeyEvent(frames, pid, type, code, hotkey, overlay)
            
    def parse_transfer_event(self, buffer, frames, type, code, pid):
        def read_resource(buffer):
            block = buffer.read_int(BIG_ENDIAN)
            base, multiplier, extension = block >> 8, block & 0xF0, block & 0x0F
            return base*multiplier+extension
            
        target = code >> 4
        buffer.skip(1)   #84
        minerals,vespene = read_resource(buffer), read_resource(buffer)
        buffer.skip(8)
        
        return ResourceTransferEvent(frames, pid, type, code, target, minerals, vespene)
        
class Unknown2Parser(object):
    def parse_0206_event(self, buffer, frames, type, code, pid):
        buffer.skip(8)
        return UnknownEvent(frames, pid, type, code)
        
    def parse_0207_event(self, buffer, frames, type, code, pid):
        buffer.skip(4)
        return UnknownEvent(frames, pid, type, code)
        
    def parse_020E_event(self, buffer, frames, type, code, pid):
        buffer.skip(4)
        return UnknownEvent(frames, pid, type, code)
        
class CameraParser(object):
    def parse_camera87_event(self, buffer, frames, type, code, pid):
        buffer.skip(8)
        return CameraMovementEvent(frames, pid, type, code)

    def parse_camera08_event(self, buffer, frames, type, code, pid):
        buffer.skip( (buffer.read_short(BIG_ENDIAN) & 0x0F) << 3 )
        return CameraMovementEvent(frames, pid, type, code)
        
    def parse_camera18_event(self, buffer, frames, type, code, pid):
        buffer.skip(162)
        return CameraMovementEvent(frames, pid, type, code)
        
    def parse_cameraX1_event(self, buffer, frames, type, code, pid):
        #Get the X and Y,  last byte is also a flag
        buffer.skip(3)
        flag = buffer.read_byte()

        if flag & 0x10 != 0:
            buffer.skip(1)
            flag = buffer.read_byte()
        if flag & 0x20 != 0:
            buffer.skip(1)
            flag = buffer.read_byte()
        if flag & 0x40 != 0:
            buffer.skip(2)
            
        return CameraMovementEvent(frames, pid, type, code)
        
class Unknown4Parser(object):
    def parse_0416_event(self, buffer, frames, type, code, pid):
        buffer.skip(24)
        return UnknownEvent(frames, pid, type, code)
        
    def parse_04C6_event(self, buffer, frames, type, code, pid):
        buffer.skip(16)
        return UnknownEvent(frames, pid, type, code)
        
    def parse_0487_event(self, buffer, frames, type, code, pid):
        buffer.skip(4) #Always 00 00 00 01 ??
        return UnknownEvent(frames, pid, type, code)
        
    def parse_0400_event(self, buffer, frames, type, code, pid):
        buffer.skip(10)
        return UnknownEvent(frames, pid, type, code)
        
    def parse_04X2_event(self, buffer, frames, type, code, pid):
        buffer.skip(2)
        return UnknownEvent(frames, pid, type, code)
        
    def parse_04XC_event(self, buffer, frames, type, code, pid):
        #no body
        return UnknownEvent(frames, pid, type, code)
