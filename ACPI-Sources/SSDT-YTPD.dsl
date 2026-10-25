// Lenovo Yoga14s 82G2, FJCN65WW, ELAN HID-over-I2C trackpad on I2C1.
// Windows identifies TPD0 with ELAN0001 and compatible ID PNP0C50.
// OEM DSDT maps ELAN0001 to address 0x15 and HID descriptor register 1.
// Requires the two exact, DSDT-only TPD0 method renames in the staged config.
DefinitionBlock ("", "SSDT", 2, "YOGA", "YTPD", 0x00000001)
{
    External (_SB.PC00.I2C1.TPD0, DeviceObj)
    External (_SB.PC00.I2C1.TPD0.XSTA, MethodObj)
    External (_SB.PC00.I2C1.TPD0.XINI, MethodObj)
    External (_SB.PC00.I2C1.TPD0._HID, StrObj)
    External (_SB.PC00.I2C1.TPD0._SUB, StrObj)
    External (_SB.PC00.I2C1.TPD0.BADR, BuffFieldObj)
    External (_SB.PC00.I2C1.TPD0.SPED, BuffFieldObj)
    External (_SB.PC00.I2C1.TPD0.HID2, IntObj)

    Scope (_SB.PC00.I2C1.TPD0)
    {
        Method (_STA, 0, NotSerialized)
        {
            If (_OSI ("Darwin"))
            {
                Return (0x0F)
            }
            Return (XSTA ())
        }

        Method (_INI, 0, Serialized)
        {
            // Preserve the OEM GPIO/pad setup. Do not write TPDT/TPVD NVS fields.
            XINI ()
            If (_OSI ("Darwin"))
            {
                _HID = "MSFT0001"
                _SUB = "ELAN0001"
                BADR = 0x15
                HID2 = One
                // Retain the OEM bus speed when it is valid.
                If ((SPED < 0x000186A0) || (SPED > 0x000F4240))
                {
                    SPED = 0x00061A80
                }
            }
        }
        // Keep the OEM _CRS/_DSM: they use BADR/SPED/HID2 updated above.
        // Existing SSDT-XOSI supplies OSYS >= 2012; force-polling stays enabled.
    }
}
