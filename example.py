import asyncio
import SmpScrPy

S = SmpScrPy.SmpScr("cnt")

async def main():


    print ("async was starterd")




if __name__ == "__main__":
    print("hello")
    asyncio.run(main())

    # 1. Звичайний текст зі спецсимволами
    text1 = 'Це текст з <тегами>, "лапками" та & амперсандами.'
    print(S.sanitize_xml_string(text1))
    # Виведе: Це текст з &lt;тегами&gt;, &quot;лапками&quot; та &amp; амперсандами.

    # 2. Заборонені керівні символи (Control Characters)
    # Наприклад, \x00 (Null byte), \x01 (Start of Heading), \x08 (Backspace)
    text2 = 'Привіт\x00Світ\x01Тут\x08Там'
    print(repr(S.sanitize_xml_string(text2)))
    # Виведе: 'ПривітСвітТутТам' (заборонені символи вирізані)

    # 3. Збереження дозволених переносів рядків та табів
    text3 = 'Рядок 1\nРядок 2\tТаб'
    print(repr(S.sanitize_xml_string(text3)))
    # Виведе: 'Рядок 1\nРядок 2\tТаб' (\n і \t залишаються, бо \x0A і \x09 дозволені в XML)

    # 4. Сурогатні пари (Surrogates) - суворо заборонені в XML 1.0
    text4 = 'Пошкодований текст: \uD800'
    print(repr(S.sanitize_xml_string(text4)))
    # Виведе: 'Пошкоджений текст: ' (сурогат видалено)

    # 5. Дійсні 4-байтові Emoji (дозволені в XML 1.0)
    text5 = 'Усмішка: 😊'
    print(S.sanitize_xml_string(text5))
    # Виведе: Усмішка: 😊
    S.finish()