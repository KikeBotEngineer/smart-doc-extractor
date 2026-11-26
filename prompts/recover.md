Revisa este documento ({label}). Para los campos de la lista se propuso un valor que no se encontró escrito en el documento.

Para cada campo, devuelve el valor exactamente como aparece en el documento, o null si no aparece. No calcules, no deduzcas, no completes.
- Usa el nombre del campo tal como está en la lista. Los índices empiezan en 0: `line_items[0]` es la primera partida.
- Cada campo de una partida trae entre paréntesis los otros valores de esa misma partida: úsalos para ubicar su renglón.
- Respeta la ortografía del documento aunque parezca un error.
- Montos como número, sin símbolo de moneda ni separadores de miles.
- Fechas en formato AAAA-MM-DD, o AAAA-MM cuando el campo lo indique.

Campos (nombre: valor propuesto):
{fields}

Documento:

{document}
