"""
Migration script to add avatar column and sample story data with images
"""
import sqlite3

conn = sqlite3.connect('app.db')
c = conn.cursor()

# Add avatar column to users table
try:
    c.execute('ALTER TABLE users ADD COLUMN avatar TEXT')
    print('✓ Added avatar column to users table')
except Exception as e:
    print(f'Avatar column already exists: {e}')

# Sample Vietnamese Fairy Tales with cover images from Unsplash
sample_stories = [
    {
        'title': 'Tấm Cám',
        'category_id': 1,  # Cổ tích Việt Nam
        'country': 'VN',
        'min_age': 3,
        'max_age': 12,
        'duration_minutes': 15,
        'summary': 'Câu chuyện về cô gái Tấm hiền lành phải chịu nhiều đau khổ từ mẹ kế và em gái Cám, nhưng cuối cùng được hưởng hạnh phúc.',
        'content': '''Ngày xưa, có một cô gái tên là Tấm sống với mẹ kế và em gái tên là Cám. Mẹ kế rất ác độc, bắt Tấm làm hết mọi việc trong nhà.

Một hôm, mẹ kế bảo hai chị em đi bắt tôm tép. Ai bắt được nhiều sẽ được thưởng một yếm đào. Tấm chăm chỉ bắt được đầy giỏ, nhưng Cám lừa Tấm đi gội đầu rồi đổ hết tôm vào giỏ mình.

Tấm khóc nức nở, có Bụt hiện lên và tặng cho Tấm một con cá bống. Tấm nuôi cá trong giếng, ngày ngày ra cho cá ăn và tâm sự.

Mẹ kế biết chuyện, bắt cá bống ăn thịt. Tấm lại được Bụt giúp, bảo tìm xương cá chôn trong bốn góc giường.

Đến ngày vua mở hội, Bụt cho Tấm quần áo đẹp và đôi hài xinh xắn. Trên đường về, Tấm đánh rơi một chiếc hài. Vua nhặt được và quyết tìm người xỏ vừa.

Cuối cùng, chỉ có Tấm là xỏ vừa chiếc hài. Vua rước Tấm về làm vợ. Tấm sống hạnh phúc trong cung điện.''',
        'cover_image': 'https://images.unsplash.com/photo-1578662996442-48f60103fc96?w=400&h=300&fit=crop',
        'is_active': 1
    },
    {
        'title': 'Sọ Dừa',
        'category_id': 1,
        'country': 'VN',
        'min_age': 3,
        'max_age': 12,
        'duration_minutes': 12,
        'summary': 'Chuyện kể về một chàng trai xấu xí như quả dừa nhưng có tấm lòng lương thiện, cuối cùng được hạnh phúc.',
        'content': '''Ngày xưa có đôi vợ chồng nghèo, hiếm muộn con cái. Một hôm bà vợ vào rừng hái củi, uống nước từ sọ dừa và mang thai.

Bà sinh ra một đứa bé không có tay chân, tròn như quả dừa. Người ta gọi là Sọ Dừa. Tuy xấu xí nhưng Sọ Dừa rất thông minh.

Lớn lên, Sọ Dừa đi chăn bò cho phú ông. Con gái phú ông thương hại, ngày ngày mang cơm cho Sọ Dừa. Nàng phát hiện Sọ Dừa thực ra là một chàng trai tuấn tú.

Sọ Dừa xin cưới con gái phú ông. Phú ông thách cưới nhiều thứ quý. Nhờ phép màu, Sọ Dừa đáp ứng được hết.

Trong đám cưới, Sọ Dừa trút bỏ lớp vỏ xấu xí, hiện thành chàng trai đẹp đẽ. Từ đó, hai vợ chồng sống hạnh phúc bên nhau.''',
        'cover_image': 'https://images.unsplash.com/photo-1509316975850-ff9c5deb0cd9?w=400&h=300&fit=crop',
        'is_active': 1
    },
    {
        'title': 'Thạch Sanh',
        'category_id': 1,
        'country': 'VN',
        'min_age': 5,
        'max_age': 15,
        'duration_minutes': 20,
        'summary': 'Câu chuyện về người anh hùng Thạch Sanh chiến đấu với yêu quái và giành được công chúa.',
        'content': '''Thạch Sanh là một chàng trai nghèo, sống một mình dưới gốc đa. Chàng kết nghĩa huynh đệ với Lý Thông - một người buôn rượu xảo quyệt.

Nhà vua lập miếu thờ chằn tinh để tế mạng người. Lý Thông lừa Thạch Sanh canh miếu. Thạch Sanh diệt được chằn tinh và lấy được cây đàn thần.

Lý Thông cướp công, được làm quan. Thạch Sanh lại bị lừa xuống hang diệt đại bàng cứu công chúa. Lý Thông lấp hang nhốt Thạch Sanh.

Nhờ cây đàn thần, công chúa nhận ra người cứu mình. Thạch Sanh được giải oan, Lý Thông bị trừng phạt.

Thạch Sanh cưới công chúa, sống hạnh phúc. Cây đàn của chàng có phép lạ, ai nghe tiếng đàn đều thấy lòng an vui.''',
        'cover_image': 'https://images.unsplash.com/photo-1533461502717-83546f485d24?w=400&h=300&fit=crop',
        'is_active': 1
    },
    {
        'title': 'Cây Khế',
        'category_id': 1,
        'country': 'VN',
        'min_age': 3,
        'max_age': 10,
        'duration_minutes': 10,
        'summary': 'Bài học về lòng tham qua câu chuyện hai anh em và con chim thần.',
        'content': '''Ngày xưa có hai anh em, cha mẹ mất sớm để lại tài sản. Người anh tham lam lấy hết ruộng vườn, chỉ để lại cho em một cây khế.

Em chăm sóc cây khế chu đáo. Mùa khế chín, có con chim lạ đến ăn. Người em than thở, chim bảo: "Ăn một quả, trả cục vàng, may túi ba gang, mang đi mà đựng."

Em may túi ba gang, chim đưa đến đảo vàng. Em lấy vừa đủ, trở về sống sung sướng.

Người anh nghe chuyện, đổi hết tài sản lấy cây khế. Khi gặp chim, anh may túi chín gang. Vì quá nặng vàng, chim bay không nổi, rơi xuống biển. Người anh mất hết.

Bài học: Lòng tham đem lại tai họa.''',
        'cover_image': 'https://images.unsplash.com/photo-1457530378978-8bac673b8062?w=400&h=300&fit=crop',
        'is_active': 1
    },
    {
        'title': 'Sự Tích Trầu Cau',
        'category_id': 1,
        'country': 'VN',
        'min_age': 5,
        'max_age': 15,
        'duration_minutes': 12,
        'summary': 'Câu chuyện về tình anh em và nguồn gốc tục ăn trầu của người Việt.',
        'content': '''Ngày xưa có hai anh em Tân và Lang giống nhau như đúc. Họ yêu thương nhau rất mực.

Tân lấy vợ, Lang ở chung. Một hôm chị dâu nhầm Lang là chồng mình. Lang xấu hổ bỏ đi, đến bên sông thì chết, hóa thành tảng đá vôi.

Tân đi tìm em, đến bên tảng đá thì chết, hóa thành cây cau. Người vợ đi tìm chồng, chết bên cây cau, hóa thành dây trầu quấn quanh thân cau.

Vua Hùng nghe chuyện, nhai trầu với vôi thấy hương vị đặc biệt, tạo thành miếng trầu têm đỏ au.

Từ đó tục ăn trầu ra đời, tượng trưng cho tình nghĩa vợ chồng, anh em son sắt.''',
        'cover_image': 'https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?w=400&h=300&fit=crop',
        'is_active': 1
    },
    {
        'title': 'Cô Bé Lọ Lem',
        'category_id': 2,  # Cổ tích thế giới
        'country': 'FOREIGN',
        'min_age': 3,
        'max_age': 12,
        'duration_minutes': 15,
        'summary': 'Câu chuyện cổ tích nổi tiếng về cô gái mồ côi và giấc mơ gặp hoàng tử.',
        'content': '''Ngày xửa ngày xưa, có một cô gái tên là Cinderella sống với mẹ kế và hai chị em cùng mẹ khác cha độc ác. Họ bắt cô làm việc nhà nặng nhọc từ sáng đến tối.

Một hôm, vua tổ chức dạ hội để chọn vợ cho hoàng tử. Hai người chị được đi dự tiệc, còn Cinderella phải ở nhà.

Bà tiên hiện lên, biến bí ngô thành xe ngựa, chuột thành người hầu, và cho cô bộ váy lộng lẫy cùng đôi hài thủy tinh. Nhưng phép màu chỉ kéo dài đến nửa đêm.

Tại dạ hội, hoàng tử say mê nàng. Khi đồng hồ điểm 12 tiếng, cô vội chạy và đánh rơi chiếc hài thủy tinh.

Hoàng tử đi khắp nơi tìm người xỏ vừa chiếc hài. Cuối cùng, chỉ có Cinderella là xỏ vừa. Hoàng tử rước nàng về cung, hai người sống hạnh phúc mãi mãi.''',
        'cover_image': 'https://images.unsplash.com/photo-1518709268805-4e9042af9f23?w=400&h=300&fit=crop',
        'is_active': 1
    },
    {
        'title': 'Nàng Bạch Tuyết',
        'category_id': 2,
        'country': 'FOREIGN',
        'min_age': 3,
        'max_age': 12,
        'duration_minutes': 18,
        'summary': 'Công chúa Bạch Tuyết và bảy chú lùn - câu chuyện về lòng tốt chiến thắng cái ác.',
        'content': '''Ngày xưa có một công chúa tên Bạch Tuyết có làn da trắng như tuyết, môi đỏ như hoa hồng, tóc đen như gỗ mun.

Hoàng hậu độc ác ganh ghét nhan sắc của nàng. Bà ta sai thợ săn giết Bạch Tuyết nhưng ông không nỡ, thả nàng vào rừng.

Bạch Tuyết tìm được căn nhà nhỏ của bảy chú lùn. Các chú lùn thương yêu và che chở cho nàng.

Hoàng hậu biết Bạch Tuyết còn sống, giả làm bà lão bán táo độc. Bạch Tuyết ăn táo và thiếp đi.

Một hoàng tử đi ngang, nhìn thấy nàng và trao nụ hôn. Bạch Tuyết tỉnh dậy. Hoàng tử đưa nàng về cung làm hoàng hậu. Họ sống hạnh phúc mãi mãi.''',
        'cover_image': 'https://images.unsplash.com/photo-1542273917363-3b1817f69a2d?w=400&h=300&fit=crop',
        'is_active': 1
    },
    {
        'title': 'Thần Thoại Sơn Tinh Thủy Tinh',
        'category_id': 3,  # Thần thoại
        'country': 'VN',
        'min_age': 5,
        'max_age': 15,
        'duration_minutes': 14,
        'summary': 'Thần thoại Việt Nam về cuộc chiến giữa thần núi và thần nước.',
        'content': '''Vua Hùng thứ 18 có con gái là Mỵ Nương xinh đẹp tuyệt trần. Hai vị thần cùng đến cầu hôn: Sơn Tinh - thần núi và Thủy Tinh - thần nước.

Vua không biết gả cho ai, bèn ra điều kiện: Ai đem sính lễ đến trước sẽ được cưới nàng. Sính lễ gồm: voi chín ngà, gà chín cựa, ngựa chín hồng mao.

Sơn Tinh đến trước, rước Mỵ Nương về núi Tản Viên. Thủy Tinh tức giận, dâng nước đánh Sơn Tinh.

Sơn Tinh dùng phép bốc núi, nước dâng bao nhiêu núi cao bấy nhiêu. Thủy Tinh kiệt sức phải rút lui.

Từ đó, hàng năm Thủy Tinh vẫn dâng nước báo thù, gây ra lũ lụt. Sơn Tinh luôn thắng, bảo vệ nhân dân.''',
        'cover_image': 'https://images.unsplash.com/photo-1506905925346-21bda4d32df4?w=400&h=300&fit=crop',
        'is_active': 1
    }
]

# Insert sample stories
for story in sample_stories:
    try:
        c.execute('''
            INSERT INTO stories (title, category_id, country, min_age, max_age, 
                                duration_minutes, summary, content, cover_image, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (story['title'], story['category_id'], story['country'], story['min_age'],
              story['max_age'], story['duration_minutes'], story['summary'], 
              story['content'], story['cover_image'], story['is_active']))
        print(f"✓ Added story: {story['title']}")
    except sqlite3.IntegrityError:
        print(f"Story already exists: {story['title']}")
    except Exception as e:
        print(f"Error adding {story['title']}: {e}")

conn.commit()
print('\n✓ Migration completed!')

# Show count
c.execute('SELECT COUNT(*) FROM stories')
count = c.fetchone()[0]
print(f'Total stories in database: {count}')

conn.close()
