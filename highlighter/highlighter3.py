from binaryninja import *
from ..utils.utils import extract_hlil_operations
import re

class Highlighter3(BackgroundTaskThread):
    def __init__(self,bv,current_address,current_function,color,type):
        self.progress_banner = f"[VulnFanatic] Running the highlight of {type}"
        BackgroundTaskThread.__init__(self, self.progress_banner, True)
        self.current_view = bv
        self.current_address = current_address
        self.current_function = current_function
        self.color = color
        self.type = type
        self.color_set = {
            "Black": binaryninja.highlight.HighlightStandardColor.BlackHighlightColor,
            "Blue": binaryninja.highlight.HighlightStandardColor.BlueHighlightColor,
            "Cyan": binaryninja.highlight.HighlightStandardColor.CyanHighlightColor,
            "Green": binaryninja.highlight.HighlightStandardColor.GreenHighlightColor,
            "Magenta": binaryninja.highlight.HighlightStandardColor.MagentaHighlightColor,
            "Orange": binaryninja.highlight.HighlightStandardColor.OrangeHighlightColor,
            "Red": binaryninja.highlight.HighlightStandardColor.RedHighlightColor,
            "White": binaryninja.highlight.HighlightStandardColor.WhiteHighlightColor,
            "Yellow": binaryninja.highlight.HighlightStandardColor.YellowHighlightColor
        }

    def run(self):
        #log_info(str(self.is_in_list(["hello",2,"world"],["1",2,3,"hello",2,"world",4])))
        if self.type == "Assembly Blocks":
            self.highlight_assembly_blocks()
        elif self.type == "HLIL Variable":
            self.highlight_hlil_var()
        elif self.type == "HLIL Blocks":
            self.highlight_hlil_blocks()
        elif self.type == "clear":
            self.clear()

    def clear(self):
        current_hlil = self.current_function.hlil
        current_hlil_instructions = list(current_hlil.instructions)
        for instruction in current_hlil_instructions:
            self.current_function.set_auto_instr_highlight(instruction.address,binaryninja.highlight.HighlightStandardColor.NoHighlightColor)
        for b in self.current_function.basic_blocks:
            b.set_auto_highlight(binaryninja.highlight.HighlightStandardColor.NoHighlightColor) 
        for b in self.current_function.hlil.basic_blocks:
            b.set_auto_highlight(binaryninja.highlight.HighlightStandardColor.NoHighlightColor) 

    def highlight_assembly_blocks(self):
        visited_blocks = []
        blocks = []
        blocks.append(self.current_function.get_low_level_il_at(self.current_address).il_basic_block)
        while blocks:
            current_block = blocks.pop()
            visited_blocks.append(f"{current_block}@{current_block.function.name}")
            #if current_block.start == 0 and "All functions" in self.type:
            #    blocks.extend(self.get_address_xref(current_block.function.start))
            current_block.set_auto_highlight(self.color_set[self.color]) 
            for edge in current_block.incoming_edges:
                if f"{edge.source.start}@{edge.source.function.name}" not in visited_blocks:
                    blocks.append(edge.source)
                    visited_blocks.append(f"{edge.source.start}@{edge.source.function.name}")

    def highlight_hlil_blocks(self):
        visited_blocks = []
        blocks = []
        current_hlil = self.current_function.hlil
        #current_hlil_instructions = list(current_hlil.instructions)
        for ins in current_hlil_instructions:
            if ins.address == self.current_address:
                blocks.append(ins.il_basic_block)
        while blocks:
            current_block = blocks.pop()
            visited_blocks.append(f"{current_block}@{current_block.function.name}")
            #if current_block.start == 0 and "All functions" in self.type:
            #    blocks.extend(self.get_address_xref(current_block.function.start))
            current_block.set_auto_highlight(self.color_set[self.color]) 
            for edge in current_block.incoming_edges:
                if f"{edge.source.start}@{edge.source.function.name}" not in visited_blocks:
                    blocks.append(edge.source)
                    visited_blocks.append(f"{edge.source.start}@{edge.source.function.name}")

    def highlight_hlil_var(self):
        trace_vars = []
        current_hlil = self.current_function.hlil
        current_hlil_instructions = list(current_hlil.instructions)
        for ins in current_hlil_instructions:
            if ins.address == self.current_address:
                variables = extract_hlil_operations(current_hlil,[HighLevelILOperation.HLIL_VAR],specific_instruction=ins)
                calls = extract_hlil_operations(current_hlil,[HighLevelILOperation.HLIL_CALL,HighLevelILOperation.HLIL_TAILCALL],specific_instruction=ins)
                for call in calls:
                    try:
                        variables = set(variables.extend(call.params))
                    except:
                        pass
                variables = list(set(variables))
                var_choice = get_choice_input(f"Available variables for instruction:\n {hex(self.current_address)} {str(ins)}","Choose variable",variables)
                if var_choice != None:
                    trace_vars = self.prepare_relevant_variables(variables[var_choice])
                    self.current_function.set_auto_instr_highlight(self.current_address,self.color_set[self.color])
        for instruction in current_hlil_instructions:
            for var in trace_vars["possible_values"]:
                # Remove when fixed
                try:
                    if re.search(var,str(instruction)):
                        log_info(str(self.expand_operands(instruction)))
                        self.current_function.set_auto_instr_highlight(instruction.address,self.color_set[self.color])
                except re.error:
                    pass

    def prepare_relevant_variables(self,param):
        vars = {
            "possible_values": [],
            "vars": [],
            "orig_vars": {}
        }
        param_vars_hlil = extract_hlil_operations(param.function,[HighLevelILOperation.HLIL_VAR],specific_instruction=param)
        param_vars = []
        original_value = str(param)
        for p in param_vars_hlil:
            vars["orig_vars"][str(p)] = []
            param_vars.append(p.var)
        for param_var in vars["orig_vars"]:
            # For each of the original variables find its possible alternatives
            for var in param_vars:
                if var not in vars["orig_vars"][param_var]:
                    vars["orig_vars"][param_var].append(var)
                    vars["vars"].append(var)
                definitions = param.function.get_var_definitions(var)
                # Also uses are relevant
                definitions.extend(param.function.get_var_uses(var))
                for d in definitions:
                    if (d.operation == HighLevelILOperation.HLIL_VAR_INIT or d.operation == HighLevelILOperation.HLIL_ASSIGN) and type(d.src.postfix_operands[0]) == Variable and d.src.postfix_operands[0] not in vars["orig_vars"][param_var]:
                        vars["orig_vars"][param_var].append(d.src.postfix_operands[0])
                        param_vars.append(d.src.postfix_operands[0])
                    elif (d.operation == HighLevelILOperation.HLIL_VAR_INIT or d.operation == HighLevelILOperation.HLIL_ASSIGN) and d.src.operation == HighLevelILOperation.HLIL_CALL:
                        # Handle assignments from calls
                        for param in d.src.params:
                            if type(param.postfix_operands[0]) == Variable and param.postfix_operands[0] not in vars["orig_vars"][param_var]:
                                vars["orig_vars"][param_var].append(param.postfix_operands[0])
                                param_vars.append(param.postfix_operands[0])
                    elif d.operation == HighLevelILOperation.HLIL_VAR and str(d) not in vars["orig_vars"][param_var]:
                        vars["orig_vars"][param_var].append(d.var)
            for v in vars["orig_vars"][param_var]:
                tmp = re.escape(re.sub(f'{param_var}\.\w+|:\d+\.\w+', str(v), original_value))
                tmp2 = tmp.replace(str(v), str(v)+"((:\\d+\\.\\w+)?\\b|\\.\\w+\\b)?")
                if tmp2 not in vars["possible_values"]:
                    vars["possible_values"].append(tmp2)  
        return vars

    def is_in_list(self,sublist,full_list):
        sublist_size = len(sublist)
        full_list_size = len(full_list)
        if sublist_size < full_list_size:
            for i in range(0,full_list_size-sublist_size+1):
                log_info(f"{sublist} vs. {full_list[i:i+sublist_size]}")
                if sublist == full_list[i:i+sublist_size]:
                    return True
        return False

    def expand_operands(self,operands):
        if type(operands) == binaryninja.HighLevelILInstruction:
            op = [operands]
        else:
            op = operands.copy()
        ret_val = []
        while op:
            current_op = op.pop(0)
            if type(current_op) == binaryninja.HighLevelILInstruction:
                op[0:0] = current_op.operands
            elif type(current_op) is list:
                op[0:0] = current_op
            else:
                ret_val.append(current_op)
        return ret_val