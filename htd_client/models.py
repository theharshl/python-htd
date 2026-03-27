from dataclasses import dataclass

@dataclass
class ZoneDetail:
    number: int
    enabled: bool = True
    power: bool = None
    mute: bool = None
    dnd: bool = None
    source: int = None
    volume: int = None
    treble: int = None
    bass: int = None
    balance: int = None
    name: str = None
    source_name: str = None

    def __str__(self):
        return (
            "zone_number = %s, enabled = %s, name = %s, source_name = %s, power = %s, "
            "mute = %s, dnd = %s, source = %s, volume = %s, "
            "treble = %s, bass = %s, balance = %s" %
            (
                self.number,
                self.enabled,
                self.name,
                self.source_name,
                self.power,
                self.mute,
                self.dnd,
                self.source,
                self.volume,
                self.treble,
                self.bass,
                self.balance,
            )
        )
