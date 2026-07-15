// Ghidra headless audit for the Isaac Gym CPython/NumPy compatibility patches.
// @category IsaacGym

import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressRange;
import ghidra.program.model.address.AddressSetView;
import ghidra.program.model.data.DataType;
import ghidra.program.model.data.DataTypeComponent;
import ghidra.program.model.data.Structure;
import ghidra.program.model.data.TypeDef;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import ghidra.program.model.mem.Memory;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;

public class BindingAudit extends GhidraScript {
    private static final long[] AUDIT_ADDRESSES = {
        0x76d54L, 0x76d64L,
        0xa00faL, 0x1419c4L, 0x141cfbL, 0x143bcdL,
        0xa1ca2L, 0xa1cb0L, 0xa1d80L, 0xa2b70L, 0xa2e2dL, 0xa2e3bL,
        0xa2f0eL, 0xa2f1cL, 0xa30c0L, 0xa30d0L, 0xa4160L, 0xa43caL,
        0xa43dfL, 0xa44c8L, 0xa44ddL, 0xa44ebL
    };

    private static final Map<String, byte[]> SIGNATURES = new LinkedHashMap<>();
    static {
        SIGNATURES.put("version_guard_jne", hex("0f85be000000"));
        SIGNATURES.put("version_guard_jbe", hex("0f86ae000000"));
        SIGNATURES.put("six_nops", hex("909090909090"));
        SIGNATURES.put("numpy1_elsize_rax", hex("48635020"));
        SIGNATURES.put("numpy1_elsize_rdx", hex("48635220"));
        SIGNATURES.put("numpy2_elsize_rax", hex("488b5028"));
        SIGNATURES.put("numpy2_elsize_rdx", hex("488b5228"));
        SIGNATURES.put("numpy1_names_check", hex("4883783800"));
        SIGNATURES.put("numpy2_names_check", hex("4883786800"));
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) {
            throw new IllegalArgumentException("BindingAudit.java requires one output path");
        }

        StringBuilder report = new StringBuilder();
        report.append("program=").append(currentProgram.getName()).append('\n');
        report.append("executable=").append(currentProgram.getExecutablePath()).append('\n');
        report.append("md5=").append(currentProgram.getExecutableMD5()).append('\n');
        report.append("image_base=").append(currentProgram.getImageBase()).append('\n');
        report.append("external_libraries=");
        report.append(String.join(",", currentProgram.getExternalManager().getExternalLibraryNames()));
        report.append("\npython_init_symbols=");
        LinkedHashSet<String> initSymbols = new LinkedHashSet<>();
        LinkedHashSet<Address> initAddresses = new LinkedHashSet<>();
        SymbolIterator symbols = currentProgram.getSymbolTable().getAllSymbols(true);
        while (symbols.hasNext()) {
            Symbol symbol = symbols.next();
            if (symbol.getName().startsWith("PyInit_")) {
                initSymbols.add(symbol.getName() + "@" + symbol.getAddress());
                initAddresses.add(symbol.getAddress());
            }
        }
        report.append(String.join(",", initSymbols));
        report.append("\n\nSIGNATURE_COUNTS\n");

        Memory memory = currentProgram.getMemory();
        for (Map.Entry<String, byte[]> entry : SIGNATURES.entrySet()) {
            report.append(entry.getKey()).append('=')
                .append(findAll(memory, entry.getValue()).size()).append('\n');
        }

        report.append("\nDWARF_LAYOUTS\n");
        appendStructure(report, "PyTypeObject");
        appendStructure(report, "_typeobject");
        appendStructure(report, "PyHeapTypeObject");
        appendStructure(report, "_heaptypeobject");
        appendStructure(report, "PyAsyncMethods");
        appendStructure(report, "PyArray_Descr");
        appendStructure(report, "PyArrayDescr_Proxy");
        appendStructure(report, "_PyArray_DescrNumPy2");
        appendStructure(report, "_PyArray_LegacyDescr");
        appendStructure(report, "PyArray_DescrProto");

        report.append("\nPYBIND_HEAP_OFFSET_REFERENCES\n");
        String[] heapOffsets = {
            " + 0x198]", " + 0x1a0]", " + 0x1b8]",
            " + 0x340]", " + 0x350]", " + 0x358]",
            " + 0x360]", " + 0x368]", " + 0x370]"
        };
        InstructionIterator instructions = currentProgram.getListing().getInstructions(true);
        while (instructions.hasNext()) {
            Instruction instruction = instructions.next();
            String text = instruction.toString();
            if (text.contains("[RSP") || text.contains("[RBP")) {
                continue;
            }
            boolean matched = false;
            for (String offset : heapOffsets) {
                if (text.contains(offset)) {
                    matched = true;
                    break;
                }
            }
            if (!matched) {
                continue;
            }
            Function function = currentProgram.getFunctionManager()
                .getFunctionContaining(instruction.getAddress());
            if (function == null) {
                continue;
            }
            String name = function.getName(true);
            if (name.contains("make_object_base_type") ||
                name.contains("make_new_python_type") ||
                name.equals("pybind11::detail::get_internals")) {
                report.append(instruction.getAddress()).append(' ')
                    .append(text).append(" function=")
                    .append(name).append('\n');
            }
        }

        report.append("\nPYBIND_NUMPY_OFFSET_REFERENCES\n");
        String[] numpyOffsets = {
            " + 0x18]", " + 0x19]", " + 0x1a]", " + 0x1b]",
            " + 0x1c]", " + 0x20]", " + 0x24]", " + 0x28]",
            " + 0x30]", " + 0x38]", " + 0x58]", " + 0x60]",
            " + 0x68]"
        };
        instructions = currentProgram.getListing().getInstructions(true);
        while (instructions.hasNext()) {
            Instruction instruction = instructions.next();
            String text = instruction.toString();
            if (text.contains("[RSP") || text.contains("[RBP")) {
                continue;
            }
            boolean matched = false;
            for (String offset : numpyOffsets) {
                if (text.contains(offset)) {
                    matched = true;
                    break;
                }
            }
            if (!matched) {
                continue;
            }
            Function function = currentProgram.getFunctionManager()
                .getFunctionContaining(instruction.getAddress());
            if (function == null) {
                continue;
            }
            String name = function.getName(true);
            if (name.equals("pybind11::array::array") ||
                name.equals("pybind11::dtype::dtype") ||
                name.equals("pybind11::dtype::strip_padding") ||
                name.equals("pybind11::detail::npy_api::get") ||
                name.equals("pybind11::detail::register_structured_dtype")) {
                report.append(instruction.getAddress()).append(' ')
                    .append(text).append(" function=").append(name).append('\n');
            }
        }

        report.append("\nAUDIT_POINTS\n");
        Map<Address, Function> functions = new LinkedHashMap<>();
        for (Address address : initAddresses) {
            Function function = currentProgram.getFunctionManager().getFunctionAt(address);
            if (function != null) {
                functions.put(function.getEntryPoint(), function);
            }
        }
        for (long offset : AUDIT_ADDRESSES) {
            Address address = currentProgram.getImageBase().add(offset);
            if (!memory.contains(address)) {
                report.append(String.format("0x%x <not mapped>%n", offset));
                continue;
            }
            byte[] context = new byte[16];
            int read = memory.getBytes(address, context);
            Instruction instruction = currentProgram.getListing().getInstructionAt(address);
            if (instruction == null) {
                disassemble(address);
                instruction = currentProgram.getListing().getInstructionAt(address);
            }
            Function function = currentProgram.getFunctionManager().getFunctionContaining(address);
            report.append(String.format(
                "0x%x bytes=%s instruction=%s function=%s function_start=%s%n",
                offset,
                toHex(context, read),
                instruction == null ? "<none>" : instruction.toString(),
                function == null ? "<none>" : function.getName(true),
                function == null ? "<none>" : function.getEntryPoint().toString()
            ));
            if (function != null) {
                functions.put(function.getEntryPoint(), function);
            }
        }

        report.append("\nDECOMPILED_FUNCTIONS\n");
        DecompInterface decompiler = new DecompInterface();
        decompiler.openProgram(currentProgram);
        for (Function function : functions.values()) {
            report.append("\n--- ").append(function.getName(true)).append(" @ ")
                .append(function.getEntryPoint()).append(" ---\n");
            DecompileResults results = decompiler.decompileFunction(function, 120, monitor);
            if (results.decompileCompleted() && results.getDecompiledFunction() != null) {
                report.append(results.getDecompiledFunction().getC());
            }
            else {
                report.append("<decompile failed: ")
                    .append(results.getErrorMessage()).append(">\n");
            }
        }
        decompiler.dispose();

        Files.writeString(Path.of(args[0]), report.toString());
        println("Binding audit written to " + args[0]);
    }

    private List<Address> findAll(Memory memory, byte[] pattern) throws Exception {
        List<Address> matches = new ArrayList<>();
        AddressSetView initialized = memory.getAllInitializedAddressSet();
        for (AddressRange range : initialized) {
            Address cursor = range.getMinAddress();
            while (cursor != null && cursor.compareTo(range.getMaxAddress()) <= 0) {
                Address match = memory.findBytes(
                    cursor, range.getMaxAddress(), pattern, null, true, monitor
                );
                if (match == null) {
                    break;
                }
                matches.add(match);
                cursor = match.add(pattern.length);
            }
        }
        return matches;
    }

    private void appendStructure(StringBuilder report, String name) {
        List<DataType> matches = new ArrayList<>();
        currentProgram.getDataTypeManager().findDataTypes(name, matches);
        if (matches.isEmpty()) {
            report.append(name).append("=<not found>\n");
            return;
        }
        for (DataType dataType : matches) {
            DataType resolved = dataType;
            while (resolved instanceof TypeDef) {
                resolved = ((TypeDef) resolved).getBaseDataType();
            }
            if (!(resolved instanceof Structure)) {
                continue;
            }
            Structure structure = (Structure) resolved;
            report.append(name).append(" length=").append(structure.getLength())
                .append(" path=").append(dataType.getPathName()).append('\n');
            for (DataTypeComponent component : structure.getDefinedComponents()) {
                report.append(String.format(
                    "  +0x%x %s size=%d type=%s%n",
                    component.getOffset(),
                    component.getFieldName(),
                    component.getLength(),
                    component.getDataType().getDisplayName()
                ));
            }
            return;
        }
        report.append(name).append("=<found but not a structure>\n");
    }

    private static byte[] hex(String value) {
        byte[] data = new byte[value.length() / 2];
        for (int i = 0; i < data.length; ++i) {
            data[i] = (byte) Integer.parseInt(value.substring(i * 2, i * 2 + 2), 16);
        }
        return data;
    }

    private static String toHex(byte[] data, int length) {
        StringBuilder result = new StringBuilder();
        for (int i = 0; i < length; ++i) {
            result.append(String.format("%02x", data[i] & 0xff));
        }
        return result.toString();
    }
}
