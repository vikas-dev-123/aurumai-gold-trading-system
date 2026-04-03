"""
Sentiment Analysis module for gold-related news.
Uses pretrained transformer models (FinBERT) to analyze market sentiment.
"""

import torch
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from datetime import datetime, timedelta
import httpx
from utils.config import NEWS_API_KEY


class SentimentAnalyzer:
    """
    Sentiment analyzer using FinBERT or similar financial sentiment models.
    
    Outputs sentiment scores:
    - Positive: +1
    - Neutral: 0
    - Negative: -1
    """
    
    def __init__(self, model_name: str = "ProsusAI/finbert", device: str = None):
        """
        Initialize sentiment analyzer.
        
        Args:
            model_name: HuggingFace model name (default: FinBERT)
            device: Device for inference ('cuda' or 'cpu')
        """
        self.model_name = model_name
        
        # Set device
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)
        
        print(f"Loading sentiment model: {model_name}")
        print(f"Using device: {self.device}")
        
        # Load tokenizer and model
        try:
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
            self.model.to(self.device)
            self.model.eval()
            
            # Label mapping
            self.label_map = {0: 'negative', 1: 'neutral', 2: 'positive'}
            
            print("✓ Model loaded successfully")
        except Exception as e:
            print(f"⚠ Error loading model: {e}")
            print("⚠ Using fallback rule-based sentiment analysis")
            self.model = None
            self.tokenizer = None
    
    def predict_sentiment(self, text: str) -> tuple:
        """
        Predict sentiment of a single text.
        
        Args:
            text: Input text
        
        Returns:
            Tuple of (sentiment_label, sentiment_score)
        """
        if self.model is None or self.tokenizer is None:
            return self._rule_based_sentiment(text)
        
        # Tokenize
        inputs = self.tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=512,
            return_tensors='pt'
        )
        
        # Move to device
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Get predictions
        with torch.no_grad():
            outputs = self.model(**inputs)
            probabilities = torch.softmax(outputs.logits, dim=-1)
        
        # Get predicted class and confidence
        predicted_class = torch.argmax(probabilities, dim=-1).item()
        confidence = probabilities[0, predicted_class].item()
        
        # Map to sentiment score (-1 to +1)
        if predicted_class == 0:  # Negative
            sentiment_score = -confidence
        elif predicted_class == 2:  # Positive
            sentiment_score = confidence
        else:  # Neutral
            sentiment_score = 0.0
        
        sentiment_label = self.label_map[predicted_class]
        
        return sentiment_label, sentiment_score
    
    def _rule_based_sentiment(self, text: str) -> tuple:
        """
        Fallback rule-based sentiment analysis.
        
        Args:
            text: Input text
        
        Returns:
            Tuple of (sentiment_label, sentiment_score)
        """
        positive_words = [
            'gain', 'rise', 'increase', 'surge', 'rally', 'bullish', 'profit',
            'optimistic', 'positive', 'growth', 'breakout', 'strength', 'high'
        ]
        
        negative_words = [
            'loss', 'drop', 'decline', 'fall', 'crash', 'bearish', 'downturn',
            'pessimistic', 'negative', 'weakness', 'low', 'sell-off', 'plunge'
        ]
        
        text_lower = text.lower()
        
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        total = positive_count + negative_count
        
        if total == 0:
            return 'neutral', 0.0
        
        score = (positive_count - negative_count) / total
        
        if score > 0.1:
            label = 'positive'
        elif score < -0.1:
            label = 'negative'
        else:
            label = 'neutral'
        
        return label, np.clip(score, -1, 1)
    
    def analyze_batch(self, texts: list) -> dict:
        """
        Analyze sentiment of multiple texts.
        
        Args:
            texts: List of texts
        
        Returns:
            Dictionary with aggregated sentiment metrics
        """
        if not texts:
            return {
                'average_score': 0.0,
                'label': 'neutral',
                'count': 0
            }
        
        scores = []
        labels = []
        
        for text in texts:
            label, score = self.predict_sentiment(text)
            scores.append(score)
            labels.append(label)
        
        avg_score = np.mean(scores)
        
        # Determine overall label
        if avg_score > 0.2:
            overall_label = 'positive'
        elif avg_score < -0.2:
            overall_label = 'negative'
        else:
            overall_label = 'neutral'
        
        return {
            'average_score': float(avg_score),
            'label': overall_label,
            'count': len(texts),
            'scores': scores,
            'labels': labels
        }


class NewsFetcher:
    """
    Fetches gold-related news from various sources.
    """
    
    def __init__(self, api_key: str = NEWS_API_KEY):
        """
        Initialize news fetcher.
        
        Args:
            api_key: NewsAPI key
        """
        self.api_key = api_key
        self.base_url = "https://newsapi.org/v2/everything"
    
    def fetch_gold_news(self, query: str = "gold price", days: int = 7,
                        language: str = "en", sort_by: str = "publishedAt") -> list:
        """
        Fetch news articles about gold.
        
        Args:
            query: Search query
            days: Number of days back to fetch
            language: Language code
            sort_by: Sort order
        
        Returns:
            List of news articles
        """
        if not self.api_key or self.api_key == "your_news_api_key_here":
            print("⚠ No API key provided. Using mock news data.")
            return self._get_mock_news()
        
        from_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        params = {
            'q': query,
            'from': from_date,
            'language': language,
            'sortBy': sort_by,
            'apiKey': self.api_key
        }
        
        try:
            response = httpx.get(self.base_url, params=params, timeout=10.0)
            response.raise_for_status()
            
            data = response.json()
            articles = data.get('articles', [])
            
            print(f"✓ Fetched {len(articles)} news articles")
            return articles
            
        except Exception as e:
            print(f"✗ Error fetching news: {e}")
            return self._get_mock_news()
    
    def _get_mock_news(self) -> list:
        """
        Generate mock news articles for testing.
        
        Returns:
            List of mock news articles
        """
        mock_articles = [
            {
                'title': 'Gold Prices Surge Amid Economic Uncertainty',
                'description': 'Investors flock to safe-haven assets as market volatility increases.',
                'publishedAt': datetime.now().isoformat(),
                'source': {'name': 'Financial Times'}
            },
            {
                'title': 'Federal Reserve Policy Impacts Gold Market',
                'description': 'Interest rate decisions continue to influence precious metals trading.',
                'publishedAt': (datetime.now() - timedelta(days=1)).isoformat(),
                'source': {'name': 'Reuters'}
            },
            {
                'title': 'Gold ETF Inflows Reach Record Highs',
                'description': 'Institutional investors increase exposure to gold-backed securities.',
                'publishedAt': (datetime.now() - timedelta(days=2)).isoformat(),
                'source': {'name': 'Bloomberg'}
            },
            {
                'title': 'Technical Analysis: Gold Tests Key Resistance Level',
                'description': 'Traders watch critical price levels for potential breakout signals.',
                'publishedAt': (datetime.now() - timedelta(days=3)).isoformat(),
                'source': {'name': 'MarketWatch'}
            },
            {
                'title': 'Central Banks Continue Gold Accumulation',
                'description': 'Global central banks maintain strategic gold reserves amid currency concerns.',
                'publishedAt': (datetime.now() - timedelta(days=4)).isoformat(),
                'source': {'name': 'CNBC'}
            }
        ]
        
        return mock_articles


def get_market_sentiment(analyzer: SentimentAnalyzer, news_fetcher: NewsFetcher,
                         days: int = 7) -> dict:
    """
    Get overall market sentiment for gold.
    
    Args:
        analyzer: Sentiment analyzer instance
        news_fetcher: News fetcher instance
        days: Number of days to analyze
    
    Returns:
        Dictionary with sentiment metrics
    """
    # Fetch news
    articles = news_fetcher.fetch_gold_news(days=days)
    
    if not articles:
        return {
            'sentiment_score': 0.0,
            'sentiment_label': 'neutral',
            'article_count': 0,
            'timestamp': datetime.now()
        }
    
    # Extract text for analysis
    texts = []
    for article in articles:
        title = article.get('title', '')
        description = article.get('description', '')
        combined = f"{title} {description}".strip()
        if combined:
            texts.append(combined)
    
    # Analyze sentiment
    sentiment_result = analyzer.analyze_batch(texts)
    
    result = {
        'sentiment_score': sentiment_result['average_score'],
        'sentiment_label': sentiment_result['label'],
        'article_count': sentiment_result['count'],
        'articles_analyzed': texts[:5],  # Store first 5 for reference
        'timestamp': datetime.now()
    }
    
    print(f"\nMarket Sentiment Analysis:")
    print(f"  Articles analyzed: {result['article_count']}")
    print(f"  Sentiment: {result['sentiment_label']} ({result['sentiment_score']:.3f})")
    
    return result


# Create singleton instance
_sentiment_analyzer = None
_news_fetcher = None


def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get or create sentiment analyzer instance."""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer()
    return _sentiment_analyzer


def get_news_fetcher() -> NewsFetcher:
    """Get or create news fetcher instance."""
    global _news_fetcher
    if _news_fetcher is None:
        _news_fetcher = NewsFetcher()
    return _news_fetcher


def analyze_current_sentiment() -> dict:
    """
    Analyze current market sentiment for gold.
    
    Returns:
        Dictionary with sentiment metrics
    """
    analyzer = get_sentiment_analyzer()
    fetcher = get_news_fetcher()
    
    return get_market_sentiment(analyzer, fetcher)


if __name__ == "__main__":
    print("=" * 60)
    print("Testing Sentiment Analysis Module")
    print("=" * 60)
    
    # Test sentiment analysis
    result = analyze_current_sentiment()
    
    print("\nFinal Result:")
    print(f"  Score: {result['sentiment_score']:.3f}")
    print(f"  Label: {result['sentiment_label']}")
    print(f"  Articles: {result['article_count']}")
