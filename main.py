import pygame
pygame.init()

FPS_LIMIT: int = 60
BLINK_DELAY: float = 0.5        # In seconds.

class Root:
    fg: tuple[int, int, int] = (255, 255, 255)
    bg: tuple[int, int, int] = (0, 0, 0)
    font_name: str = "Arial"
    font_size: int = 18

window = pygame.display.set_mode((500, 500), pygame.RESIZABLE)
window.fill(Root.bg)
font = pygame.font.SysFont(Root.font_name, Root.font_size)
clock = pygame.time.Clock()
pygame.display.set_caption("Virtual Terminal (by Jadon Zufall)")


class Channel:
    C_NAN: int      = 0x00 | 0x00
    C_OUT: int      = 0x10 | 0x01
    C_OUT_CMD: int  = 0x10 | 0x01
    C_IN: int       = 0x20 | 0x00
    C_IN_CMD: int   = 0x20 | 0x01


    _dat: list[str]

    def __init__(self) -> None:
        self._dat = list()
    
    def put(self, s: str) -> None:
        self._dat.append(s)

    def fput(self, s: str, *args, **kwargs) -> None:
        self.put(s.format(*args, **kwargs))

    def clear(self) -> None:
        self._dat = list()
    
    def pop(self, idx: int=-1) -> str:
        return self._dat.pop(idx)

    @staticmethod
    def is_subtype_of(a: int, b: int) -> bool:
        return a >> 4 == b >> 4
    
    @property
    def ctype(self) -> int: return Channel.C_NAN

class OutputChannel(Channel):
    def get(self) -> str:
        return self._dat
    
    @property
    def ctype(self): return Channel.C_OUT

class TerminalOutputChannel(OutputChannel):
    _lc_opt: bool
    def __init__(self) -> None:
        super().__init__()
        self._lc_opt = False
    
    def get(self) -> str:
        result = []
        if not self._lc_opt:
            return OutputChannel.get(self)
        for idx, val in enumerate(OutputChannel.get(self)):
            result.append(f"[{idx}] {val}")
        return result

    def _quote_join(self, *args: str) -> list[str]:
        result = []
        storage = []
        in_quotes: bool = False
        for idx, txt in enumerate(args):
            if txt.startswith("\"") and txt.endswith("\"") and not in_quotes:
                result.append(txt)
                continue
            elif txt.startswith("\"") and not in_quotes:
                storage.append(txt)
                in_quotes = True
                continue
            elif txt.endswith("\"") and in_quotes:
                storage.append(txt)
                in_quotes = False
                result.append("".join(storage))
                storage = list()
                continue
            elif txt.startswith("\""):
                raise ValueError
            elif txt.endswith("\""):
                raise ValueError
            else:
                result.append(txt)
        if len(storage) != 0:
            raise ValueError
        return result
    
    def _parse_cmd(self, s: str, ignore: int) -> str:
        return s[ignore:]

    def _clear_command(self, *args: str) -> None:
        print(args)
        if len(args) == 1:
            self._dat = list()
            return
        print(len(args))
        if len(args) > 3:
            self.raw_put("Bad arguments (too many args)")
            return
        if len(args) == 3:
            if args[1] == "-r":
                self._dat.pop()
            else:
                self.raw_put("Bad arguments (args[1] != valid flag)")
        try:
            line = int(args[-1])
            self._dat.pop(line)
        except ValueError:
            self.raw_put("Bad arguments (args[-1] != int)")
            return
    
    def _unknown_command(self, *args: str) -> None:
        self.raw_put(f"Unknown Command \"{args[0]}\"")
    
    def _help_command(self, *args: str) -> None:
        #TODO: Write help command later
        self.raw_put(f"Only god can help you now!  (#TODO: Write help command later)")
    
    def _out_command(self, *args: str) -> None:
        if len(args) == 1:
            self.raw_put("")
            return
        
        try:
            jargs = self._quote_join(*args[1:])
        except ValueError:
            self.raw_put("Bad quote")
            return
        
        if len(jargs) != 1:
            self.raw_put("Bad arguments?")
            return None
        
        if jargs[-1].startswith("\"") and jargs[-1].endswith("\""):
            self.raw_put(jargs[-1][1:-1])
            return
        
        self.raw_put(jargs[-1])
    
    def _lc_command(self, *args: str) -> None:
        self._lc_opt = True
        
    
    def raw_put(self, s: str) -> None:
        OutputChannel.put(self, s)

    def put(self, s: str, ignore: int=0) -> None:
        self.raw_put(s)

        commands: list[str] = self._parse_cmd(s, ignore).split(";")
        
        for cmd in commands:
            args: list[str] = cmd.split(" ")
            args: list[str] = list(filter(lambda x: len(x) != 0, args))
            if len(args) == 0:
                continue
            self.run_command(*args)

    def run_command(self, *args: str) -> None:
        if args[0] == "clear":
            self._clear_command(*args)
        elif args[0] == "help":
            self._help_command(*args)
        elif args[0] == "out":
            self._out_command(*args)
        elif args[0] == "lc":
            self._lc_command(*args)
        else:
            self._unknown_command(*args)

    @property
    def ctype(self) -> int: return Channel.C_OUT_CMD

class InputChannel(Channel):
    def get(self) -> str:
        return "".join(self._dat)

    @property
    def ctype(self) -> int: return Channel.C_IN


class TerminalInputChannel(InputChannel):
    _head: str

    def __init__(self, head: str | None = None) -> None:
        super().__init__()
        self._head = head
        if self._head is None:
            self._head = ""
    
    def get(self) -> str:
        return self._head + InputChannel.get(self)
    
    def set_head(self, head: str | None) -> None:
        self._head = head
        if self._head is None:
            self._head = ""
    
    def get_head(self) -> str:
        return self._head

    @property
    def ctype(self) -> int: return Channel.C_OUT_CMD

class IOPair:
    _i: InputChannel
    _o: OutputChannel
    def __init__(self, i: InputChannel | None=None, o: OutputChannel | None=None) -> None:
        self._i = i
        if self._i is None:
            self._i = InputChannel()
        self._o = o
        if self._o is None:
            self._o = OutputChannel()
    
    @property
    def input(self) -> InputChannel:
        return self._i
    
    @property
    def output(self) -> OutputChannel:
        return self._o



class KeyContext:
    def __init__(self) -> None:
        pass

    def __call__(self, event: pygame.event.Event):
        pass


class DefaultKeyContext(KeyContext):
    _i: TerminalInputChannel
    _o: TerminalOutputChannel

    def __init__(self, io: IOPair) -> None:
        super().__init__()
        self._i = io.input
        self._o = io.output
    
    def __call__(self, event: pygame.event.Event):
        if event.key == pygame.K_BACKSPACE:
            _ = self._i.pop(idx=-1)
    
        elif event.key == pygame.K_RETURN:
            self._o.put(self._i.get(), ignore=len(self._i.get_head()))
            self._i.clear()
    
        else:
            self._i.put(event.unicode)



class RenderContext:
    dst: pygame.Surface

    def __init__(self, dst: pygame.Surface) -> None:
        self.dst = dst
    
    def __call__(self, dt: int) -> None:
        pass

class DefaultRenderContext(RenderContext):
    _i: TerminalInputChannel
    _o: TerminalOutputChannel
    
    blink_timer: int

    def __init__(self, dst: pygame.Surface, io: IOPair) -> None:
        super().__init__(dst)
        self._i = io.input
        self._o = io.output

        self.blink_timer = 0

    def __call__(self, dt: int) -> None:
        self.dst.fill(Root.bg)
        
        x_offset: int = 0
        y_offset: int = 0

        for idx, line in enumerate(self._o.get()):
            src = font.render(line, True, Root.fg, None)
            self.dst.blit(src, (x_offset, y_offset))
            y_offset += src.get_height()

        src = font.render(f"{self._i.get()}", True, Root.fg, None)
        self.dst.blit(src, (x_offset, y_offset))
        x_offset += src.get_width()

        if self.blink_timer > FPS_LIMIT * (BLINK_DELAY + BLINK_DELAY):
            self.blink_timer = 0
        
        elif self.blink_timer > FPS_LIMIT * BLINK_DELAY:
            src = font.render(f"_", True, Root.fg, None)
            self.dst.blit(src, (x_offset, y_offset))
        
        else:
            src = font.render(f"_", True, Root.bg, None)
            self.dst.blit(src, (x_offset, y_offset))

        self.blink_timer += 1


def test() -> None:
    assert Channel.is_subtype_of(Channel.C_IN, Channel.C_IN_CMD)
    assert Channel.is_subtype_of(Channel.C_OUT, Channel.C_OUT_CMD)
    assert not Channel.is_subtype_of(Channel.C_OUT, Channel.C_IN_CMD)
    assert not Channel.is_subtype_of(Channel.C_IN, Channel.C_OUT_CMD)
    
test()

    
ROOT_IO: IOPair = IOPair(i=TerminalInputChannel(head=">>> "), o=TerminalOutputChannel())
key_context: KeyContext = DefaultKeyContext(io=ROOT_IO)
render_context: RenderContext = DefaultRenderContext(dst=window, io=ROOT_IO)

user_input: str = ""
is_running: bool = True

while is_running:
    dt = clock.tick(FPS_LIMIT)
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            is_running = False
        elif event.type == pygame.KEYDOWN:
            key_context(event)
    
    render_context(dt)
    pygame.display.flip()