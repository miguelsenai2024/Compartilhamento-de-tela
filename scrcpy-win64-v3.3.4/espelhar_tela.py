import subprocess
import time
import os

# Constante específica do Windows para não abrir a tela preta do CMD em segundo plano
CREATE_NO_WINDOW = 0x08000000

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADB_PATH = os.path.join(SCRIPT_DIR, "adb.exe")
SCRCPY_PATH = os.path.join(SCRIPT_DIR, "scrcpy.exe")


class QrCode:
    def __init__(self, version, errcorlvl, data_codewords, msk):
        self._version = version
        self._errcorlvl = errcorlvl
        self._size = version * 4 + 17
        self._mask = msk
        self._modules = [[False] * self._size for _ in range(self._size)]
        self._isfunction = [[False] * self._size for _ in range(self._size)]
        self._draw_function_patterns()
        allcodewords = self._add_ecc_and_interleave(bytearray(data_codewords))
        self._draw_codewords(allcodewords)
        self._apply_mask(msk)
        self._draw_format_bits(msk)

    def get_size(self):
        return self._size

    def get_module(self, x, y):
        return self._modules[y][x]

    @staticmethod
    def encode_text(text):
        segs = [QrSegment.make_bytes(text.encode("utf-8"))]
        return QrCode.encode_segments(segs)

    @staticmethod
    def encode_segments(segs, ecl=1, minversion=1, maxversion=40, mask=-1, boostecl=True):
        if not (1 <= minversion <= maxversion <= 40) or mask < -1 or mask > 7:
            raise ValueError("Parâmetros inválidos")
        for version in range(minversion, maxversion + 1):
            datacapacitybits = QrCode._get_num_data_codewords(version, ecl) * 8
            datausedbits = QrSegment.get_total_bits(segs, version)
            if datausedbits is not None and datausedbits <= datacapacitybits:
                break
        else:
            raise ValueError("Dados muito longos")
        if boostecl:
            for newecl in range(3, ecl - 1, -1):
                if datausedbits <= QrCode._get_num_data_codewords(version, newecl) * 8:
                    ecl = newecl
                    break
        bb = _BitBuffer()
        for seg in segs:
            bb.append_bits(seg.get_mode().get_mode_bits(), 4)
            bb.append_bits(seg.get_num_chars(), seg.get_mode().num_char_count_bits(version))
            bb.extend(seg.get_data())
        bb.append_bits(0, min(4, datacapacitybits - len(bb)))
        bb.append_bits(0, (-len(bb)) % 8)
        padbyte = 0xEC
        while len(bb) < datacapacitybits:
            bb.append_bits(padbyte, 8)
            padbyte ^= 0xEC ^ 0x11
        datacodewords = bytearray(bb.get_bytes())
        if mask == -1:
            minpenalty = 10**9
            bestmask = 0
            for m in range(8):
                qr = QrCode(version, ecl, datacodewords, m)
                penalty = qr._get_penalty_score()
                if penalty < minpenalty:
                    minpenalty = penalty
                    bestmask = m
            mask = bestmask
        return QrCode(version, ecl, datacodewords, mask)

    def _draw_function_patterns(self):
        for i in range(self._size):
            self._set_function_module(6, i, i % 2 == 0)
            self._set_function_module(i, 6, i % 2 == 0)
        self._draw_finder_pattern(3, 3)
        self._draw_finder_pattern(self._size - 4, 3)
        self._draw_finder_pattern(3, self._size - 4)
        self._draw_separators()
        self._draw_alignment_patterns()
        self._draw_version()

    def _draw_finder_pattern(self, x, y):
        for dy in range(-4, 5):
            for dx in range(-4, 5):
                xx = x + dx
                yy = y + dy
                if 0 <= xx < self._size and 0 <= yy < self._size:
                    dist = max(abs(dx), abs(dy))
                    self._set_function_module(xx, yy, dist != 2 and dist != 4)

    def _draw_separators(self):
        for i in range(8):
            self._set_function_module(7, i, False)
            self._set_function_module(i, 7, False)
            self._set_function_module(self._size - 8, i, False)
            self._set_function_module(self._size - 1 - i, 7, False)
            self._set_function_module(7, self._size - 1 - i, False)
            self._set_function_module(i, self._size - 8, False)

    def _draw_alignment_patterns(self):
        pos = QrCode._get_alignment_pattern_positions(self._version)
        numalign = len(pos)
        for i in range(numalign):
            for j in range(numalign):
                if (i == 0 and j == 0) or (i == 0 and j == numalign - 1) or (i == numalign - 1 and j == 0):
                    continue
                self._draw_alignment_pattern(pos[i], pos[j])

    def _draw_alignment_pattern(self, x, y):
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                self._set_function_module(x + dx, y + dy, max(abs(dx), abs(dy)) != 1)

    def _set_function_module(self, x, y, isblack):
        self._modules[y][x] = isblack
        self._isfunction[y][x] = True

    def _draw_format_bits(self, mask):
        data = self._errcorlvl << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        for i in range(0, 6):
            self._set_function_module(8, i, ((bits >> i) & 1) != 0)
        self._set_function_module(8, 7, ((bits >> 6) & 1) != 0)
        self._set_function_module(8, 8, ((bits >> 7) & 1) != 0)
        self._set_function_module(7, 8, ((bits >> 8) & 1) != 0)
        for i in range(9, 15):
            self._set_function_module(14 - i, 8, ((bits >> i) & 1) != 0)
        for i in range(0, 8):
            self._set_function_module(self._size - 1 - i, 8, ((bits >> i) & 1) != 0)
        for i in range(8, 15):
            self._set_function_module(8, self._size - 15 + i, ((bits >> i) & 1) != 0)
        self._set_function_module(8, self._size - 8, True)

    def _draw_version(self):
        if self._version < 7:
            return
        rem = self._version
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = self._version << 12 | rem
        for i in range(18):
            bit = ((bits >> i) & 1) != 0
            a = self._size - 11 + i % 3
            b = i // 3
            self._set_function_module(a, b, bit)
            self._set_function_module(b, a, bit)

    def _draw_codewords(self, data):
        i = 0
        for right in range(self._size - 1, 0, -2):
            if right == 6:
                right = 5
            for vert in range(self._size):
                for j in range(2):
                    x = right - j
                    upward = ((right + 1) & 2) == 0
                    y = self._size - 1 - vert if upward else vert
                    if not self._isfunction[y][x] and i < len(data) * 8:
                        self._modules[y][x] = ((data[i >> 3] >> (7 - (i & 7))) & 1) != 0
                        i += 1

    def _apply_mask(self, mask):
        for y in range(self._size):
            for x in range(self._size):
                if self._isfunction[y][x]:
                    continue
                invert = False
                if mask == 0:
                    invert = (x + y) % 2 == 0
                elif mask == 1:
                    invert = y % 2 == 0
                elif mask == 2:
                    invert = x % 3 == 0
                elif mask == 3:
                    invert = (x + y) % 3 == 0
                elif mask == 4:
                    invert = (x // 3 + y // 2) % 2 == 0
                elif mask == 5:
                    invert = (x * y) % 2 + (x * y) % 3 == 0
                elif mask == 6:
                    invert = ((x * y) % 2 + (x * y) % 3) % 2 == 0
                elif mask == 7:
                    invert = ((x + y) % 2 + (x * y) % 3) % 2 == 0
                if invert:
                    self._modules[y][x] = not self._modules[y][x]

    def _get_penalty_score(self):
        result = 0
        for y in range(self._size):
            runcolor = False
            runx = 0
            for x in range(self._size):
                color = self._modules[y][x]
                if x == 0:
                    runcolor = color
                    runx = 1
                elif color == runcolor:
                    runx += 1
                    if runx == 5:
                        result += 3
                    elif runx > 5:
                        result += 1
                else:
                    runcolor = color
                    runx = 1
        for x in range(self._size):
            runcolor = False
            runy = 0
            for y in range(self._size):
                color = self._modules[y][x]
                if y == 0:
                    runcolor = color
                    runy = 1
                elif color == runcolor:
                    runy += 1
                    if runy == 5:
                        result += 3
                    elif runy > 5:
                        result += 1
                else:
                    runcolor = color
                    runy = 1
        for y in range(self._size - 1):
            for x in range(self._size - 1):
                c = self._modules[y][x]
                if c == self._modules[y][x + 1] == self._modules[y + 1][x] == self._modules[y + 1][x + 1]:
                    result += 3
        for y in range(self._size):
            bits = 0
            for x in range(self._size):
                bits = ((bits << 1) & 0x7FF) | (1 if self._modules[y][x] else 0)
                if x >= 10 and (bits == 0x05D or bits == 0x5D0):
                    result += 40
        for x in range(self._size):
            bits = 0
            for y in range(self._size):
                bits = ((bits << 1) & 0x7FF) | (1 if self._modules[y][x] else 0)
                if y >= 10 and (bits == 0x05D or bits == 0x5D0):
                    result += 40
        black = sum(1 for row in self._modules for c in row if c)
        total = self._size * self._size
        k = abs(black * 20 - total * 10) // total
        result += k * 10
        return result

    @staticmethod
    def _get_alignment_pattern_positions(ver):
        if ver == 1:
            return []
        numalign = ver // 7 + 2
        step = 26 if ver == 32 else ((ver * 4 + numalign * 2 + 1) // (2 * numalign - 2)) * 2
        result = [6]
        for i in range(numalign - 2):
            result.append(ver * 4 + 10 - i * step)
        result.append(ver * 4 + 10)
        return list(reversed(result))

    @staticmethod
    def _get_num_data_codewords(ver, ecl):
        return (QrCode._get_num_raw_data_modules(ver) // 8) - QrCode._ECC_CODEWORDS_PER_BLOCK[ecl][ver] * QrCode._NUM_ERROR_CORRECTION_BLOCKS[ecl][ver]

    @staticmethod
    def _get_num_raw_data_modules(ver):
        result = (16 * ver + 128) * ver + 64
        if ver >= 2:
            numalign = ver // 7 + 2
            result -= (25 * numalign - 10) * numalign - 55
            if ver >= 7:
                result -= 36
        return result

    def _add_ecc_and_interleave(self, data):
        ver = self._version
        ecl = self._errcorlvl
        numblocks = QrCode._NUM_ERROR_CORRECTION_BLOCKS[ecl][ver]
        blockeclen = QrCode._ECC_CODEWORDS_PER_BLOCK[ecl][ver]
        rawcodewords = QrCode._get_num_raw_data_modules(ver) // 8
        numshortblocks = numblocks - rawcodewords % numblocks
        shortblocklen = rawcodewords // numblocks
        blocks = []
        k = 0
        rs = _ReedSolomonGenerator(blockeclen)
        for i in range(numblocks):
            datlen = shortblocklen - blockeclen + (0 if i < numshortblocks else 1)
            dat = data[k:k + datlen]
            k += datlen
            ecc = rs.get_remainder(dat)
            if i < numshortblocks:
                dat += b"\x00"
            blocks.append(dat + ecc)
        result = bytearray()
        for i in range(max(len(b) for b in blocks)):
            for b in blocks:
                if i < len(b):
                    result.append(b[i])
        return result

    _ECC_CODEWORDS_PER_BLOCK = (
        None,
        (None, 7, 10, 15, 20, 26, 18, 20, 24, 30, 18, 20, 24, 26, 30, 22, 24, 28, 30, 28, 28, 28, 28, 30, 30, 26, 28, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30, 30),
        (None, 10, 16, 26, 36, 48, 64, 72, 88, 110, 130, 150, 176, 198, 216, 240, 280, 308, 338, 364, 416, 442, 476, 504, 560, 588, 644, 700, 728, 784, 812, 868, 924, 980, 1036, 1064, 1120, 1204, 1260, 1316, 1372),
        (None, 13, 22, 36, 52, 72, 96, 108, 132, 160, 192, 224, 260, 288, 320, 360, 408, 448, 504, 546, 600, 644, 690, 750, 810, 870, 952, 1020, 1050, 1140, 1200, 1290, 1350, 1440, 1530, 1590, 1680, 1770, 1860, 1950, 2040),
    )
    _NUM_ERROR_CORRECTION_BLOCKS = (
        None,
        (None, 1, 1, 1, 1, 1, 2, 2, 2, 2, 4, 4, 4, 4, 4, 6, 6, 6, 6, 7, 8, 8, 9, 9, 10, 12, 12, 12, 13, 14, 15, 16, 17, 18, 19, 19, 20, 21, 22, 24, 25),
        (None, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25, 26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49, 51),
        (None, 1, 1, 2, 2, 4, 4, 6, 6, 8, 8, 10, 12, 16, 12, 17, 16, 18, 21, 20, 23, 23, 25, 27, 29, 34, 34, 35, 38, 40, 43, 45, 48, 51, 53, 56, 59, 62, 65, 68, 71),
    )


class QrSegment:
    class Mode:
        def __init__(self, modebits, charcountbits):
            self._modebits = modebits
            self._charcountbits = charcountbits

        def get_mode_bits(self):
            return self._modebits

        def num_char_count_bits(self, ver):
            return self._charcountbits[(ver + 7) // 17]

    BYTE = Mode(0x4, (8, 16, 16))

    def __init__(self, mode, numchars, data):
        self._mode = mode
        self._numchars = numchars
        self._data = data

    def get_mode(self):
        return self._mode

    def get_num_chars(self):
        return self._numchars

    def get_data(self):
        return self._data

    @staticmethod
    def make_bytes(data):
        bb = _BitBuffer()
        for b in data:
            bb.append_bits(b, 8)
        return QrSegment(QrSegment.BYTE, len(data), bb)

    @staticmethod
    def get_total_bits(segs, ver):
        result = 0
        for seg in segs:
            ccbits = seg.get_mode().num_char_count_bits(ver)
            if seg.get_num_chars() >= (1 << ccbits):
                return None
            result += 4 + ccbits + len(seg.get_data())
        return result


class _BitBuffer(list):
    def append_bits(self, val, n):
        if n < 0 or val >> n != 0:
            raise ValueError("Bits inválidos")
        for i in reversed(range(n)):
            self.append(((val >> i) & 1) != 0)

    def get_bytes(self):
        result = bytearray()
        for i in range(0, len(self), 8):
            b = 0
            for j in range(8):
                b = (b << 1) | (1 if i + j < len(self) and self[i + j] else 0)
            result.append(b)
        return result


class _ReedSolomonGenerator:
    def __init__(self, degree):
        if degree < 1 or degree > 255:
            raise ValueError("Grau inválido")
        self._coefficients = bytearray([0] * (degree - 1) + [1])
        root = 1
        for _ in range(degree):
            for j in range(degree):
                self._coefficients[j] = self._multiply(self._coefficients[j], root)
                if j + 1 < degree:
                    self._coefficients[j] ^= self._coefficients[j + 1]
            root = self._multiply(root, 0x02)

    def get_remainder(self, data):
        result = bytearray([0] * len(self._coefficients))
        for b in data:
            factor = b ^ result[0]
            result = result[1:] + b"\x00"
            for i in range(len(result)):
                result[i] ^= self._multiply(self._coefficients[i], factor)
        return result

    @staticmethod
    def _multiply(x, y):
        z = 0
        for i in range(7, -1, -1):
            z = (z << 1) ^ ((z >> 7) * 0x11D)
            if ((y >> i) & 1) != 0:
                z ^= x
        return z


def _run_adb(args):
    cmd = [ADB_PATH] + args
    return subprocess.run(cmd, capture_output=True, text=True, creationflags=CREATE_NO_WINDOW)


def _list_online_devices():
    result = _run_adb(["devices"])
    output = result.stdout.strip().split("\n")
    devices = []
    for line in output[1:]:
        line = line.strip()
        if not line:
            continue
        if "\tdevice" in line and "\toffline" not in line:
            devices.append(line.split("\t")[0])
    return devices

def ensure_connected_device():
    """Garante que existe um dispositivo ADB online via cabo (USB) antes de iniciar o scrcpy."""
    if not os.path.exists(ADB_PATH):
        print("❌ Erro: 'adb.exe' não foi encontrado na mesma pasta do script.")
        return None

    if not os.path.exists(SCRCPY_PATH):
        print("❌ Erro: 'scrcpy.exe' não foi encontrado na mesma pasta do script.")
        return None

    devices = _list_online_devices()
    if not devices:
        print("❌ Nenhum celular detectado.")
        print("Verifique se:")
        print(" 1. O cabo USB está conectado.")
        print(" 2. A 'Depuração USB' está ativada no celular.")
        print(" 3. A tela do celular está desbloqueada e você aceitou a permissão do PC.")
        return None

    if len(devices) == 1:
        device = devices[0]
        print(f"✅ Celular detectado: {device}. Inicializando a tela...")
        return device

    # Multiple devices, prefer USB
    usb_devices = [d for d in devices if ':' not in d]
    if usb_devices:
        device = usb_devices[0]
        print(f"✅ Múltiplos dispositivos detectados. Usando USB: {device}. Inicializando a tela...")
        return device

    print("❌ Múltiplos dispositivos detectados, mas nenhum USB. Dispositivos:")
    for d in devices:
        print(f"  - {d}")
    print("Conecte apenas um dispositivo USB ou especifique manualmente.")
    return None

def start_screen_mirror(device):
    """Abre a tela do celular no PC usando o scrcpy."""
    try:
        process = subprocess.Popen(
            [SCRCPY_PATH, '-s', device, '--stay-awake'],
            creationflags=CREATE_NO_WINDOW
        )
        
        print("🚀 Tela espelhada com sucesso! (A tela do celular continua ligada)")
        print("(Feche a janela do celular no PC para encerrar)")
        
        # O script Python aguarda você fechar a janela do celular para finalizar
        process.wait()
        print("Sessão de espelhamento encerrada.")

    except FileNotFoundError:
        print("❌ Erro: O 'scrcpy' não foi encontrado no seu Windows. Reinicie o PC após a instalação.")

if __name__ == "__main__":
    print("=" * 40)
    print("  INICIALIZADOR DE TELA - WINDOWS 10  ")
    print("=" * 40)
    
    device = ensure_connected_device()
    if device:
        time.sleep(1)  # Pausa rápida
        start_screen_mirror(device)
