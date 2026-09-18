"""Validadores de digito de control.

Sirven para exigir que un patron numerico sea realmente un identificador y no
una cifra cualquiera. Sin ellos, reglas como la de tarjeta de credito generarian
falsos positivos con cualquier secuencia larga de digitos.
"""

import re

_DNI_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIE_PREFIX = {"X": "0", "Y": "1", "Z": "2"}


def valid_rut(value: str) -> bool:
    """RUT/RUN chileno, modulo 11. El digito verificador puede ser 'K'."""
    body = re.sub(r"[^0-9kK]", "", value)
    if not (8 <= len(body) <= 9):
        return False
    number, dv = body[:-1], body[-1].upper()
    if not number.isdigit():
        return False
    total, factor = 0, 2
    for digit in reversed(number):
        total += int(digit) * factor
        factor = 2 if factor == 7 else factor + 1
    rest = 11 - (total % 11)
    expected = "0" if rest == 11 else "K" if rest == 10 else str(rest)
    return expected == dv


def valid_dni(value: str) -> bool:
    """DNI espanol: 8 digitos + letra de control (modulo 23)."""
    cleaned = re.sub(r"[^0-9A-Za-z]", "", value).upper()
    if len(cleaned) != 9 or not cleaned[:8].isdigit():
        return False
    return _DNI_LETTERS[int(cleaned[:8]) % 23] == cleaned[8]


def valid_nie(value: str) -> bool:
    """NIE espanol: X/Y/Z + 7 digitos + letra de control."""
    cleaned = re.sub(r"[^0-9A-Za-z]", "", value).upper()
    if len(cleaned) != 9 or cleaned[0] not in _NIE_PREFIX or not cleaned[1:8].isdigit():
        return False
    number = int(_NIE_PREFIX[cleaned[0]] + cleaned[1:8])
    return _DNI_LETTERS[number % 23] == cleaned[8]


def valid_cif(value: str) -> bool:
    """CIF espanol: letra de organizacion + 7 digitos + digito/letra de control."""
    cleaned = re.sub(r"[^0-9A-Za-z]", "", value).upper()
    if len(cleaned) != 9 or cleaned[0] not in "ABCDEFGHJNPQRSUVW" or not cleaned[1:8].isdigit():
        return False
    digits = cleaned[1:8]
    odd = sum(int(d) for d in digits[1::2])
    even = 0
    for d in digits[0::2]:
        doubled = int(d) * 2
        even += doubled // 10 + doubled % 10
    control = (10 - (odd + even) % 10) % 10
    last = cleaned[8]
    if cleaned[0] in "PQRSNW":                 # control siempre alfabetico
        return last == "JABCDEFGHI"[control]
    if cleaned[0] in "ABEH":                   # control siempre numerico
        return last == str(control)
    return last == str(control) or last == "JABCDEFGHI"[control]


def valid_iban(value: str) -> bool:
    """IBAN: modulo 97 sobre la cadena reordenada (ISO 13616)."""
    cleaned = re.sub(r"\s", "", value).upper()
    if not (15 <= len(cleaned) <= 34) or not cleaned[:2].isalpha() or not cleaned[2:4].isdigit():
        return False
    rearranged = cleaned[4:] + cleaned[:4]
    digits = ""
    for char in rearranged:
        if char.isdigit():
            digits += char
        elif char.isalpha():
            digits += str(ord(char) - 55)
        else:
            return False
    return int(digits) % 97 == 1


def valid_luhn(value: str) -> bool:
    """Numero de tarjeta: algoritmo de Luhn."""
    digits = re.sub(r"[^0-9]", "", value)
    if not (13 <= len(digits) <= 19):
        return False
    total, double = 0, False
    for digit in reversed(digits):
        current = int(digit)
        if double:
            current *= 2
            if current > 9:
                current -= 9
        total += current
        double = not double
    return total % 10 == 0
