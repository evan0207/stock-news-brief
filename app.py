# 해외 주식 뉴스 AI 큐레이션 MVP
# Tech Stack: Streamlit + yfinance + Google Gemini API

import streamlit as st
import yfinance as yf
import google.generativeai as genai
from datetime import datetime
import requests
import time

# ===========================
# 페이지 설정
# ===========================
st.set_page_config(
    page_title="Global Stock News AI Brief",
    page_icon="🌐",
    layout="wide"
)

# ===========================
# 자동 새로고침 설정 (30초)
# ===========================
# 세션 상태에서 자동 새로고침 설정 확인
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()

# ===========================
# 커스텀 CSS 스타일
# ===========================
st.markdown("""
<style>
    /* 메인 컨테이너 스타일 */
    .main-header {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        margin-bottom: 2rem;
        text-align: center;
        color: white;
    }
    
    /* 뉴스 카드 스타일 */
    .news-card {
        background: white;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1rem;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        border-left: 4px solid #667eea;
    }
    
    /* 감성 분석 배지 */
    .sentiment-positive {
        background-color: #d4edda;
        color: #155724;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: bold;
    }
    
    .sentiment-negative {
        background-color: #f8d7da;
        color: #721c24;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: bold;
    }
    
    .sentiment-neutral {
        background-color: #e2e3e5;
        color: #383d41;
        padding: 0.3rem 0.8rem;
        border-radius: 20px;
        font-weight: bold;
    }
    
    /* 티커 태그 */
    .ticker-tag {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 0.2rem 0.6rem;
        border-radius: 5px;
        font-size: 0.8rem;
        margin-right: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# ===========================
# 뉴스 수집 함수 (yfinance 사용)
# ===========================
def fetch_news(ticker_symbol: str, max_news: int = 5) -> list:
    """
    yfinance를 사용하여 특정 티커의 최신 뉴스를 가져옵니다.
    
    Args:
        ticker_symbol: 주식 티커 심볼 (예: AAPL, TSLA)
        max_news: 가져올 최대 뉴스 개수
    
    Returns:
        뉴스 정보 리스트 (제목, 링크, 썸네일, 발행일 등)
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        news_list = ticker.news[:max_news] if ticker.news else []
        
        processed_news = []
        for news in news_list:
            # yfinance API 구조: 뉴스 데이터가 'content' 안에 있음
            content = news.get('content', news)
            
            # 제목 추출
            title = content.get('title', news.get('title', '제목 없음'))
            
            # 링크 추출
            link = '#'
            if content.get('canonicalUrl'):
                link = content['canonicalUrl'].get('url', '#')
            elif content.get('clickThroughUrl'):
                link = content['clickThroughUrl'].get('url', '#')
            elif news.get('link'):
                link = news.get('link', '#')
            
            # 발행사 추출
            provider = content.get('provider', {})
            publisher = provider.get('displayName', news.get('publisher', '알 수 없음'))
            
            # 썸네일 추출
            thumbnail_url = None
            thumbnail_data = content.get('thumbnail', news.get('thumbnail'))
            if thumbnail_data:
                resolutions = thumbnail_data.get('resolutions', [])
                if resolutions and len(resolutions) > 0:
                    thumbnail_url = resolutions[0].get('url')
            
            # 발행일 추출
            pub_date_str = content.get('pubDate', '')
            if pub_date_str:
                try:
                    from datetime import datetime as dt_parser
                    pub_date = dt_parser.fromisoformat(pub_date_str.replace('Z', '+00:00'))
                    published = pub_date.strftime('%Y-%m-%d %H:%M')
                except:
                    published = pub_date_str[:16] if len(pub_date_str) > 16 else pub_date_str
            elif news.get('providerPublishTime'):
                published = datetime.fromtimestamp(news.get('providerPublishTime', 0)).strftime('%Y-%m-%d %H:%M')
            else:
                published = '날짜 없음'
            
            news_item = {
                'title': title,
                'link': link,
                'publisher': publisher,
                'thumbnail': thumbnail_url,
                'published': published,
                'summary': content.get('summary', ''),
                'ticker': ticker_symbol
            }
            processed_news.append(news_item)
        
        return processed_news
    except Exception as e:
        st.error(f"❌ {ticker_symbol} 뉴스 가져오기 실패: {str(e)}")
        return []

# ===========================
# 주가 차트 데이터 가져오기 함수
# ===========================
def fetch_stock_chart(ticker_symbol: str, period: str = "1mo") -> dict:
    """
    yfinance를 사용하여 주가 데이터를 가져옵니다.
    
    Args:
        ticker_symbol: 주식 티커 심볼
        period: 기간 (1d, 5d, 1mo, 3mo, 6mo, 1y)
    
    Returns:
        주가 데이터 딕셔너리 (차트 데이터, 현재가, 변동률 등)
    """
    try:
        ticker = yf.Ticker(ticker_symbol)
        
        # 기간에 따른 interval 설정 (더 세밀한 데이터)
        interval_map = {
            "5d": "15m",   # 15분 간격
            "1mo": "1h",   # 1시간 간격
            "3mo": "1d",   # 1일 간격
            "6mo": "1d",   # 1일 간격
            "1y": "1d",    # 1일 간격
            "2y": "1wk",   # 1주 간격
            "5y": "1wk",   # 1주 간격
            "max": "1mo"   # 1개월 간격
        }
        
        interval = interval_map.get(period, "1d")
        hist = ticker.history(period=period, interval=interval)
        
        if hist.empty or len(hist) < 2:
            # interval 없이 다시 시도
            hist = ticker.history(period=period)
        
        if hist.empty or len(hist) < 2:
            return None
        
        # 현재가와 변동률 계산
        current_price = float(hist['Close'].iloc[-1])
        prev_price = float(hist['Close'].iloc[0])
        change = current_price - prev_price
        change_pct = (change / prev_price) * 100 if prev_price != 0 else 0
        
        # 차트 데이터 준비 (컬럼명 변경)
        chart_df = hist[['Close']].copy()
        chart_df.columns = ['종가']  # 한글로 변경
        
        return {
            'ticker': ticker_symbol,
            'data': chart_df,
            'current_price': current_price,
            'change': change,
            'change_pct': change_pct,
            'high': float(hist['High'].max()),
            'low': float(hist['Low'].min()),
            'data_points': len(hist)
        }
    except Exception as e:
        st.error(f"❌ {ticker_symbol} 차트 데이터 가져오기 실패: {str(e)}")
        return None

# ===========================
# Gemini AI 요약 함수
# ===========================
def summarize_with_gemini(api_key: str, news_title: str, news_link: str) -> dict:
    """
    Google Gemini API를 사용하여 뉴스를 한국어로 요약하고 감성 분석합니다.
    
    Args:
        api_key: Gemini API 키
        news_title: 뉴스 제목
        news_link: 뉴스 원문 링크
    
    Returns:
        요약 결과 딕셔너리 (korean_title, summary, sentiment)
    """
    try:
        # Gemini API 설정
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 프롬프트 구성
        prompt = f"""
다음 영문 뉴스 제목을 분석해주세요:

제목: {news_title}
링크: {news_link}

다음 형식으로 정확히 응답해주세요:
1. 한국어 제목: (영문 제목을 자연스러운 한국어로 번역)
2. 3줄 요약:
• (첫 번째 핵심 포인트)
• (두 번째 핵심 포인트)  
• (세 번째 핵심 포인트 또는 시장 영향)
3. 핵심 문장:
> "(기사에서 가장 중요한 인용문 또는 핵심 문장 1)"
> "(두 번째 핵심 문장 - 있다면)"
4. 감성 분석: (호재/악재/중립 중 하나만 선택하고 간단한 이유)

주식 투자자 관점에서 분석해주세요. 핵심 문장은 기사의 핵심을 담은 실제 문장이나 주요 수치/발언을 한국어로 번역해서 인용해주세요.
"""
        
        # API 호출
        response = model.generate_content(prompt)
        response_text = response.text
        
        # 응답 파싱 (간단한 방식)
        lines = response_text.strip().split('\n')
        
        korean_title = news_title  # 기본값
        summary = ""
        key_quotes = ""
        sentiment = "중립"
        
        for i, line in enumerate(lines):
            if '한국어 제목:' in line:
                korean_title = line.split('한국어 제목:')[-1].strip()
            elif '3줄 요약:' in line:
                # 다음 줄들에서 bullet points 추출
                summary_lines = []
                for j in range(i+1, min(i+4, len(lines))):
                    if lines[j].strip().startswith('•') or lines[j].strip().startswith('-'):
                        summary_lines.append(lines[j].strip())
                summary = '\n'.join(summary_lines) if summary_lines else response_text
            elif '핵심 문장:' in line:
                # 다음 줄들에서 인용문 추출
                quote_lines = []
                for j in range(i+1, min(i+4, len(lines))):
                    stripped = lines[j].strip()
                    if stripped.startswith('>') or stripped.startswith('"') or stripped.startswith('"'):
                        quote_lines.append(stripped)
                    elif '감성 분석' in stripped:
                        break
                key_quotes = '\n'.join(quote_lines) if quote_lines else ""
            elif '감성 분석' in line or '감성분석' in line:
                sentiment_text = line.split(':')[-1].strip() if ':' in line else line
                if '호재' in sentiment_text:
                    sentiment = '호재'
                elif '악재' in sentiment_text:
                    sentiment = '악재'
                else:
                    sentiment = '중립'
        
        # 요약이 비어있으면 전체 응답 사용
        if not summary:
            summary = response_text
        
        # 감성 분석이 중립인데 전체 응답에 호재/악재가 명확히 있으면 재파싱
        if sentiment == '중립':
            # 전체 응답에서 감성 관련 라인 다시 찾기
            for line in lines:
                line_lower = line.lower()
                if '감성' in line or 'sentiment' in line_lower:
                    if '호재' in line:
                        sentiment = '호재'
                        break
                    elif '악재' in line:
                        sentiment = '악재'
                        break
            
            # 그래도 중립이면 마지막 수단으로 전체 텍스트에서 마지막으로 언급된 감성 찾기
            if sentiment == '중립':
                last_positive = response_text.rfind('호재')
                last_negative = response_text.rfind('악재')
                if last_positive > last_negative and last_positive != -1:
                    sentiment = '호재'
                elif last_negative > last_positive and last_negative != -1:
                    sentiment = '악재'
        
        return {
            'korean_title': korean_title,
            'summary': summary,
            'key_quotes': key_quotes,
            'sentiment': sentiment,
            'raw_response': response_text
        }
        
    except Exception as e:
        return {
            'korean_title': news_title,
            'summary': f'⚠️ 요약 생성 실패: {str(e)}',
            'sentiment': '중립',
            'raw_response': ''
        }

# ===========================
# 감성 분석 이모지 반환 함수
# ===========================
def get_sentiment_emoji(sentiment: str) -> str:
    """감성 분석 결과에 따른 이모지와 스타일 반환"""
    if sentiment == '호재':
        return '🟢 호재', 'sentiment-positive'
    elif sentiment == '악재':
        return '🔴 악재', 'sentiment-negative'
    else:
        return '⚪ 중립', 'sentiment-neutral'

# ===========================
# 메인 UI
# ===========================
def main():
    # 헤더
    st.markdown("""
    <div class="main-header">
        <h1>🌐 Global Stock News AI Brief</h1>
        <p>해외 주식 뉴스를 AI가 한국어로 요약해드립니다</p>
    </div>
    """, unsafe_allow_html=True)
    
    # ===========================
    # 사이드바 설정
    # ===========================
    with st.sidebar:
        st.header("⚙️ 설정")
        
        # Gemini API Key 입력
        api_key = st.text_input(
            "🔑 Gemini API Key",
            type="password",
            placeholder="API 키를 입력하세요",
            help="Google AI Studio에서 발급받은 API 키를 입력하세요"
        )
        
        st.markdown("---")
        
        # 티커 선택
        st.subheader("📊 티커 선택")
        default_tickers = ['SPY', 'QQQ', 'NVDA', 'TSLA']
        
        # 기본 티커 체크박스
        selected_tickers = st.multiselect(
            "분석할 티커를 선택하세요",
            options=['SPY', 'QQQ', 'NVDA', 'TSLA', 'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'],
            default=default_tickers
        )
        
        # 커스텀 티커 입력
        custom_ticker = st.text_input(
            "➕ 직접 입력",
            placeholder="예: AMD, COIN",
            help="추가할 티커를 쉼표로 구분하여 입력"
        )
        
        if custom_ticker:
            custom_list = [t.strip().upper() for t in custom_ticker.split(',')]
            selected_tickers.extend(custom_list)
        
        st.markdown("---")
        
        # 뉴스 개수 설정
        news_count = st.slider("📰 티커당 뉴스 개수", min_value=1, max_value=10, value=3)
        
        # 새로고침 버튼
        refresh_button = st.button("🔄 뉴스 새로고침", use_container_width=True)
        
        # 자동 새로고침 토글
        st.markdown("---")
        st.session_state.auto_refresh = st.toggle(
            "🔁 자동 새로고침 (30초)",
            value=st.session_state.auto_refresh,
            help="30초마다 차트 데이터를 자동으로 업데이트합니다"
        )
        
        if st.session_state.auto_refresh:
            st.info(f"⏱️ 마지막 업데이트: {st.session_state.last_refresh.strftime('%H:%M:%S')}")
        
        st.markdown("---")
        st.markdown("### 📌 사용 방법")
        st.markdown("""
        1. Gemini API Key 입력
        2. 원하는 티커 선택
        3. 뉴스 새로고침 클릭
        4. AI 요약 버튼으로 분석
        """)
    
    # ===========================
    # 메인 컨텐츠
    # ===========================
    if not selected_tickers:
        st.warning("⚠️ 사이드바에서 분석할 티커를 선택하세요.")
        return
    
    # 세션 상태 초기화
    if 'news_data' not in st.session_state or refresh_button:
        st.session_state.news_data = {}
        st.session_state.summaries = {}
    
    # 뉴스 수집
    with st.spinner("📡 뉴스를 수집하는 중..."):
        all_news = []
        for ticker in selected_tickers:
            if ticker not in st.session_state.news_data:
                news = fetch_news(ticker, news_count)
                st.session_state.news_data[ticker] = news
            all_news.extend(st.session_state.news_data.get(ticker, []))
    
    # 중복 기사 제거 (제목 기준)
    seen_titles = set()
    unique_news = []
    for news in all_news:
        if news['title'] not in seen_titles:
            seen_titles.add(news['title'])
            unique_news.append(news)
    all_news = unique_news
    
    if not all_news:
        st.info("🔍 수집된 뉴스가 없습니다. 다른 티커를 시도해보세요.")
        return
    
    st.success(f"✅ 총 {len(all_news)}개의 뉴스를 수집했습니다!")
    
    # ===========================
    # 주가 차트 섹션
    # ===========================
    st.markdown("## 📈 주가 차트")
    
    # 차트 기간 선택 (더 넓은 범위)
    chart_period = st.selectbox(
        "기간 선택",
        options=["5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "max"],
        format_func=lambda x: {"5d": "1주", "1mo": "1개월", "3mo": "3개월", "6mo": "6개월", "1y": "1년", "2y": "2년", "5y": "5년", "max": "전체"}[x],
        index=1  # 기본값: 1개월
    )
    
    # 티커별 차트 표시 (3개씩 행으로 나눠서 표시)
    for row_start in range(0, len(selected_tickers), 3):
        row_tickers = selected_tickers[row_start:row_start + 3]
        chart_cols = st.columns(len(row_tickers))
        
        for i, ticker in enumerate(row_tickers):
            with chart_cols[i]:
                chart_data = fetch_stock_chart(ticker, chart_period)
                
                if chart_data:
                    # 가격 변동에 따른 색상
                    color = "🟢" if chart_data['change'] >= 0 else "🔴"
                    change_sign = "+" if chart_data['change'] >= 0 else ""
                    
                    st.markdown(f"### {ticker} {color}")
                    st.metric(
                        label="현재가",
                        value=f"${chart_data['current_price']:.2f}",
                        delta=f"{change_sign}{chart_data['change_pct']:.2f}%"
                    )
                    
                    # 차트 표시
                    st.line_chart(chart_data['data'], height=200)
                    
                    # 고가/저가 정보
                    st.caption(f"📈 고: ${chart_data['high']:.2f} | 📉 저: ${chart_data['low']:.2f}")
                else:
                    st.warning(f"⚠️ {ticker} 차트 없음")
    
    st.markdown("---")
    
    # ===========================
    # 뉴스 카드 표시
    # ===========================
    for idx, news in enumerate(all_news):
        with st.container():
            col1, col2 = st.columns([1, 4])
            
            with col1:
                # 썸네일 이미지
                if news.get('thumbnail'):
                    try:
                        st.image(news['thumbnail'], width=150)
                    except:
                        st.markdown("📰")
                else:
                    st.markdown("### 📰")
                
                # 티커 태그
                st.markdown(f"<span class='ticker-tag'>{news['ticker']}</span>", unsafe_allow_html=True)
            
            with col2:
                # 뉴스 제목
                st.markdown(f"### {news['title']}")
                st.caption(f"📅 {news['published']} | 🏢 {news['publisher']}")
                
                # AI 요약 섹션
                news_key = f"{news['ticker']}_{idx}"
                
                # 이미 요약된 경우 표시
                if news_key in st.session_state.summaries:
                    summary_data = st.session_state.summaries[news_key]
                    
                    # 한국어 제목
                    st.markdown(f"**🇰🇷 {summary_data['korean_title']}**")
                    
                    # 요약
                    st.markdown(summary_data['summary'])
                    
                    # 핵심 문장 표시
                    if summary_data.get('key_quotes'):
                        st.markdown("**📌 핵심 문장:**")
                        st.info(summary_data['key_quotes'])
                    
                    # 감성 분석
                    emoji, css_class = get_sentiment_emoji(summary_data['sentiment'])
                    st.markdown(f"<span class='{css_class}'>{emoji}</span>", unsafe_allow_html=True)
                
                # 버튼 영역
                btn_col1, btn_col2 = st.columns(2)
                
                with btn_col1:
                    if st.button(f"🤖 AI 요약", key=f"summarize_{news_key}"):
                        if not api_key:
                            st.error("⚠️ 사이드바에서 Gemini API Key를 입력하세요!")
                        else:
                            with st.spinner("🧠 AI가 분석 중..."):
                                result = summarize_with_gemini(api_key, news['title'], news['link'])
                                st.session_state.summaries[news_key] = result
                                st.rerun()
                
                with btn_col2:
                    st.link_button("🔗 원문 보기", news['link'])
            
            st.markdown("---")
    
    # ===========================
    # 푸터
    # ===========================
    st.markdown("""
    <div style='text-align: center; color: #888; padding: 2rem;'>
        <p>🌐 Global Stock News AI Brief | Powered by yfinance & Google Gemini</p>
        <p>⚠️ 본 서비스는 투자 조언이 아닙니다. 투자는 본인 책임입니다.</p>
    </div>
    """, unsafe_allow_html=True)
    
    # ===========================
    # 자동 새로고침 로직 (30초)
    # ===========================
    if st.session_state.auto_refresh:
        time.sleep(30)
        st.session_state.last_refresh = datetime.now()
        st.session_state.news_data = {}  # 캐시 초기화
        st.rerun()

# ===========================
# 앱 실행
# ===========================
if __name__ == "__main__":
    main()
