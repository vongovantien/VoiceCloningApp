import sqlite3
conn = sqlite3.connect('app.db')

# Add sample stories
sample_stories = [
    {
        'title': 'Tấm Cám',
        'content': '''Ngày xửa ngày xưa, có một cô gái tên là Tấm sống với dì ghẻ và cô em cùng cha khác mẹ tên là Cám. Tấm là một cô gái hiền lành, chăm chỉ nhưng thường xuyên bị mẹ con Cám bắt nạt.

Một ngày, vua mở hội kén vợ cho hoàng tử. Tấm rất muốn đi nhưng bị mẹ ghẻ trộn gạo với thóc bắt nhặt xong mới được đi. Bụt hiện lên giúp Tấm, cho chim sẻ xuống nhặt giúp. Bụt còn biến bí thành xe, chuột thành ngựa, áo cũ thành áo đẹp và cho Tấm đôi giày thêu đỏ.

Tấm đi dự hội, hoàng tử say mê vẻ đẹp của nàng. Khi Tấm chạy vội về vì sợ trễ giờ, nàng đánh rơi một chiếc giày. Hoàng tử nhặt được và đi tìm cô gái có bàn chân vừa với chiếc giày ấy.

Cuối cùng hoàng tử tìm được Tấm, đưa nàng về cung làm hoàng hậu. Từ đó, Tấm sống hạnh phúc mãi mãi.''',
        'summary': 'Câu chuyện cổ tích về cô Tấm hiền lành chiến thắng sự gian ác của mẹ con Cám nhờ sự giúp đỡ của ông Bụt.',
        'category_id': 1,
        'country': 'VN',
        'min_age': 3,
        'max_age': 12,
        'duration_minutes': 10
    },
    {
        'title': 'Sự tích cây vú sữa',
        'content': '''Ngày xưa có một cậu bé rất nghịch ngợm. Một hôm cậu bị mẹ mắng, cậu giận mẹ bỏ đi. Mẹ cậu ngày đêm khóc thương con, ngóng con trở về.

Thương con, mẹ không ăn không ngủ, ngày ngày đứng đợi ở cửa. Cuối cùng mẹ gục xuống và biến thành một cây lạ mọc trước sân nhà.

Cậu bé lang thang mãi rồi cũng trở về nhà. Không thấy mẹ đâu, cậu ôm cây khóc. Cây run lên, lá lay động như mẹ vẫy gọi. Những quả chín rơi vào lòng cậu, thơm ngọt như dòng sữa mẹ ngày xưa.

Cậu bé khóc nức nở, hối hận vì đã không nghe lời mẹ. Từ đó, cây được gọi là cây vú sữa.''',
        'summary': 'Truyền thuyết về nguồn gốc cây vú sữa, nhắc nhở về tình mẹ bao la.',
        'category_id': 1,
        'country': 'VN',
        'min_age': 5,
        'max_age': 15,
        'duration_minutes': 5
    },
    {
        'title': 'Cô bé quàng khăn đỏ',
        'content': '''Ngày xửa ngày xưa, có một cô bé luôn đội chiếc khăn đỏ mà bà ngoại tặng, nên mọi người gọi cô là Cô bé quàng khăn đỏ.

Một hôm, mẹ bảo cô mang bánh và rượu sang thăm bà ngoại đang bị ốm. Mẹ dặn đi thẳng, không được la cà dọc đường.

Trên đường đi, cô gặp con sói. Sói hỏi cô đi đâu, cô thật thà kể. Sói chạy tắt đến nhà bà trước, nuốt chửng bà rồi đóng giả làm bà.

Khi cô bé đến, thấy bà có tai to, mắt to, mồm to. Sói nhảy ra định ăn thịt cô. May thay, bác thợ săn đi ngang nghe tiếng hét, xông vào cứu cô bé và bà ngoại.

Từ đó, cô bé không bao giờ la cà trên đường nữa.''',
        'summary': 'Câu chuyện cổ tích nổi tiếng về cô bé và con sói gian ác.',
        'category_id': 2,
        'country': 'FOREIGN',
        'min_age': 3,
        'max_age': 10,
        'duration_minutes': 8
    }
]

for story in sample_stories:
    conn.execute('''
        INSERT INTO stories (title, content, summary, category_id, country, min_age, max_age, duration_minutes, is_active)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
    ''', (story['title'], story['content'], story['summary'], story['category_id'], 
          story['country'], story['min_age'], story['max_age'], story['duration_minutes']))

conn.commit()
print("Sample stories added successfully!")

# Verify
count = conn.execute("SELECT COUNT(*) FROM stories").fetchone()[0]
print(f"Total stories: {count}")
conn.close()
