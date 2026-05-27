from kitstructlog import InitLoggers, LoggerReg


class Loggers(InitLoggers):
    main = LoggerReg(name="MAIN", level=LoggerReg.Level.INFO)
    providers = LoggerReg(name="PROVIDERS", level=LoggerReg.Level.WARNING)
    api = LoggerReg(name="API", level=LoggerReg.Level.INFO)
    development = LoggerReg(name="DEVELOPMENT", level=LoggerReg.Level.DEBUG)

    def __init__(self, *, developer_mode: bool = False) -> None:
        if developer_mode:
            for attr_name in dir(self.__class__):
                attr = getattr(self.__class__, attr_name)
                if isinstance(attr, LoggerReg) and attr.level is not LoggerReg.Level.NONE:
                    attr.level = LoggerReg.Level.DEBUG

        super().__init__(developer_mode=developer_mode)
