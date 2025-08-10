from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, func, asc
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
import json
import logging

from .market_data_tables import (
    KlineData, OrderBookSnapshot, TradeData, 
    IndicatorValue, MarketMetrics, SymbolInfo
)

logger = logging.getLogger(__name__)

class MarketDataRepository:
    def __init__(self, session: Session):
        self.session = session
    
    # Kline Data Methods
    def save_kline(self, kline_data: Dict[str, Any]) -> KlineData:
        kline = KlineData(
            symbol=kline_data['symbol'],
            interval=kline_data['interval'],
            open_time=kline_data['open_time'],
            close_time=kline_data['close_time'],
            open_price=kline_data['open_price'],
            high_price=kline_data['high_price'],
            low_price=kline_data['low_price'],
            close_price=kline_data['close_price'],
            volume=kline_data['volume'],
            quote_volume=kline_data.get('quote_volume', 0),
            number_of_trades=kline_data.get('number_of_trades'),
            taker_buy_base_volume=kline_data.get('taker_buy_base_volume'),
            taker_buy_quote_volume=kline_data.get('taker_buy_quote_volume')
        )
        
        try:
            self.session.merge(kline)
            self.session.commit()
            return kline
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving kline data: {e}")
            raise
    
    def get_klines(self, 
                   symbol: str, 
                   interval: str,
                   start_time: Optional[datetime] = None,
                   end_time: Optional[datetime] = None,
                   limit: int = 1000) -> List[KlineData]:
        query = self.session.query(KlineData).filter(
            and_(
                KlineData.symbol == symbol,
                KlineData.interval == interval
            )
        )
        
        if start_time:
            query = query.filter(KlineData.open_time >= start_time)
        if end_time:
            query = query.filter(KlineData.open_time <= end_time)
        
        return query.order_by(desc(KlineData.open_time)).limit(limit).all()
    
    def get_latest_kline(self, symbol: str, interval: str) -> Optional[KlineData]:
        return self.session.query(KlineData).filter(
            and_(
                KlineData.symbol == symbol,
                KlineData.interval == interval
            )
        ).order_by(desc(KlineData.open_time)).first()
    
    def get_earliest_kline(self, symbol: str, interval: str) -> Optional[KlineData]:
        """Get the earliest kline for a symbol/interval combination"""
        return self.session.query(KlineData).filter(
            and_(
                KlineData.symbol == symbol,
                KlineData.interval == interval
            )
        ).order_by(asc(KlineData.open_time)).first()
    
    def get_kline_by_time(self, symbol: str, interval: str, open_time: datetime) -> Optional[KlineData]:
        """Get a specific kline by its open time"""
        return self.session.query(KlineData).filter(
            and_(
                KlineData.symbol == symbol,
                KlineData.interval == interval,
                KlineData.open_time == open_time
            )
        ).first()
    
    def count_klines(self, 
                     symbol: str, 
                     interval: str,
                     start_time: Optional[datetime] = None,
                     end_time: Optional[datetime] = None) -> int:
        """Count the number of klines in a given time range"""
        query = self.session.query(func.count(KlineData.id)).filter(
            and_(
                KlineData.symbol == symbol,
                KlineData.interval == interval
            )
        )
        
        if start_time:
            query = query.filter(KlineData.open_time >= start_time)
        if end_time:
            query = query.filter(KlineData.open_time <= end_time)
        
        return query.scalar() or 0
    
    def bulk_save_klines(self, klines: List[Dict[str, Any]], batch_size: int = 1000) -> int:
        """
        Bulk save klines with efficient upsert operation
        
        Args:
            klines: List of kline dictionaries
            batch_size: Number of records to insert at once
            
        Returns:
            Number of records inserted/updated
        """
        if not klines:
            return 0
        
        total_saved = 0
        
        try:
            for i in range(0, len(klines), batch_size):
                batch = klines[i:i + batch_size]
                
                # Prepare data for bulk insert
                stmt = insert(KlineData).values(batch)
                
                # On conflict, update the existing record
                stmt = stmt.on_conflict_do_update(
                    constraint='unique_kline',
                    set_={
                        'high_price': stmt.excluded.high_price,
                        'low_price': stmt.excluded.low_price,
                        'close_price': stmt.excluded.close_price,
                        'volume': stmt.excluded.volume,
                        'quote_volume': stmt.excluded.quote_volume,
                        'number_of_trades': stmt.excluded.number_of_trades,
                        'taker_buy_base_volume': stmt.excluded.taker_buy_base_volume,
                        'taker_buy_quote_volume': stmt.excluded.taker_buy_quote_volume
                    }
                )
                
                self.session.execute(stmt)
                total_saved += len(batch)
            
            self.session.commit()
            logger.debug(f"Bulk saved {total_saved} klines")
            return total_saved
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error bulk saving klines: {e}")
            raise
    
    def get_data_gaps(self, 
                      symbol: str, 
                      interval: str,
                      start_time: datetime,
                      end_time: datetime) -> List[Tuple[datetime, datetime]]:
        """
        Find gaps in kline data for a given time range
        
        Args:
            symbol: Trading symbol
            interval: Time interval
            start_time: Start of the range to check
            end_time: End of the range to check
            
        Returns:
            List of (gap_start, gap_end) tuples representing missing data ranges
        """
        klines = self.get_klines(symbol, interval, start_time, end_time, limit=100000)
        
        if not klines:
            return [(start_time, end_time)]
        
        # Sort klines by open time
        klines.sort(key=lambda k: k.open_time)
        
        gaps = []
        
        # Check for gap at the beginning
        if klines[0].open_time > start_time:
            gaps.append((start_time, klines[0].open_time))
        
        # Check for gaps between klines
        expected_duration = self._get_interval_duration(interval)
        for i in range(len(klines) - 1):
            expected_next = klines[i].close_time + timedelta(milliseconds=1)
            actual_next = klines[i + 1].open_time
            
            if actual_next > expected_next + expected_duration:
                gaps.append((expected_next, actual_next))
        
        # Check for gap at the end
        if klines[-1].close_time < end_time:
            gaps.append((klines[-1].close_time, end_time))
        
        return gaps
    
    def _get_interval_duration(self, interval: str) -> timedelta:
        """Convert interval string to timedelta"""
        interval_map = {
            '1m': timedelta(minutes=1),
            '3m': timedelta(minutes=3),
            '5m': timedelta(minutes=5),
            '15m': timedelta(minutes=15),
            '30m': timedelta(minutes=30),
            '1h': timedelta(hours=1),
            '2h': timedelta(hours=2),
            '4h': timedelta(hours=4),
            '6h': timedelta(hours=6),
            '8h': timedelta(hours=8),
            '12h': timedelta(hours=12),
            '1d': timedelta(days=1),
            '3d': timedelta(days=3),
            '1w': timedelta(weeks=1),
            '1M': timedelta(days=30)  # Approximate
        }
        return interval_map.get(interval, timedelta(minutes=1))
    
    # Order Book Methods
    def save_orderbook_snapshot(self, orderbook_data: Dict[str, Any]) -> OrderBookSnapshot:
        snapshot = OrderBookSnapshot(
            symbol=orderbook_data['symbol'],
            timestamp=orderbook_data['timestamp'],
            update_id=orderbook_data['update_id'],
            bids_json=json.dumps(orderbook_data['bids']),
            asks_json=json.dumps(orderbook_data['asks']),
            best_bid_price=orderbook_data.get('best_bid_price'),
            best_bid_qty=orderbook_data.get('best_bid_qty'),
            best_ask_price=orderbook_data.get('best_ask_price'),
            best_ask_qty=orderbook_data.get('best_ask_qty'),
            spread=orderbook_data.get('spread')
        )
        
        try:
            self.session.add(snapshot)
            self.session.commit()
            return snapshot
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving orderbook snapshot: {e}")
            raise
    
    def get_latest_orderbook(self, symbol: str) -> Optional[OrderBookSnapshot]:
        snapshot = self.session.query(OrderBookSnapshot).filter(
            OrderBookSnapshot.symbol == symbol
        ).order_by(desc(OrderBookSnapshot.timestamp)).first()
        
        if snapshot:
            # Parse JSON fields
            snapshot.bids = json.loads(snapshot.bids_json)
            snapshot.asks = json.loads(snapshot.asks_json)
        
        return snapshot
    
    # Trade Data Methods
    def save_trade(self, trade_data: Dict[str, Any]) -> TradeData:
        trade = TradeData(
            symbol=trade_data['symbol'],
            trade_id=trade_data['trade_id'],
            price=trade_data['price'],
            quantity=trade_data['quantity'],
            quote_quantity=trade_data.get('quote_quantity', 
                                         trade_data['price'] * trade_data['quantity']),
            timestamp=trade_data['timestamp'],
            is_buyer_maker=trade_data.get('is_buyer_maker', 0)
        )
        
        try:
            self.session.merge(trade)
            self.session.commit()
            return trade
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving trade data: {e}")
            raise
    
    def get_recent_trades(self, symbol: str, limit: int = 100) -> List[TradeData]:
        return self.session.query(TradeData).filter(
            TradeData.symbol == symbol
        ).order_by(desc(TradeData.timestamp)).limit(limit).all()
    
    # Indicator Methods
    def save_indicator_value(self, indicator_data: Dict[str, Any]) -> IndicatorValue:
        indicator = IndicatorValue(
            symbol=indicator_data['symbol'],
            indicator_name=indicator_data['indicator_name'],
            timeframe=indicator_data['timeframe'],
            timestamp=indicator_data['timestamp'],
            value=indicator_data['value'],
            parameters=json.dumps(indicator_data.get('parameters', {})),
            additional_values=json.dumps(indicator_data.get('additional_values', {}))
        )
        
        try:
            self.session.merge(indicator)
            self.session.commit()
            return indicator
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving indicator value: {e}")
            raise
    
    def get_indicator_values(self,
                           symbol: str,
                           indicator_name: str,
                           timeframe: str,
                           start_time: Optional[datetime] = None,
                           limit: int = 100) -> List[IndicatorValue]:
        query = self.session.query(IndicatorValue).filter(
            and_(
                IndicatorValue.symbol == symbol,
                IndicatorValue.indicator_name == indicator_name,
                IndicatorValue.timeframe == timeframe
            )
        )
        
        if start_time:
            query = query.filter(IndicatorValue.timestamp >= start_time)
        
        indicators = query.order_by(desc(IndicatorValue.timestamp)).limit(limit).all()
        
        # Parse JSON fields
        for ind in indicators:
            ind.parameters_dict = json.loads(ind.parameters) if ind.parameters else {}
            ind.additional_values_dict = json.loads(ind.additional_values) if ind.additional_values else {}
        
        return indicators
    
    def get_latest_indicator(self,
                            symbol: str,
                            indicator_name: str,
                            timeframe: str) -> Optional[IndicatorValue]:
        indicator = self.session.query(IndicatorValue).filter(
            and_(
                IndicatorValue.symbol == symbol,
                IndicatorValue.indicator_name == indicator_name,
                IndicatorValue.timeframe == timeframe
            )
        ).order_by(desc(IndicatorValue.timestamp)).first()
        
        if indicator:
            indicator.parameters_dict = json.loads(indicator.parameters) if indicator.parameters else {}
            indicator.additional_values_dict = json.loads(indicator.additional_values) if indicator.additional_values else {}
        
        return indicator
    
    # Market Metrics Methods
    def save_market_metrics(self, metrics_data: Dict[str, Any]) -> MarketMetrics:
        metrics = MarketMetrics(
            symbol=metrics_data['symbol'],
            timestamp=metrics_data['timestamp'],
            price_24h_change=metrics_data.get('price_24h_change'),
            volume_24h=metrics_data.get('volume_24h'),
            high_24h=metrics_data.get('high_24h'),
            low_24h=metrics_data.get('low_24h'),
            open_interest=metrics_data.get('open_interest'),
            funding_rate=metrics_data.get('funding_rate'),
            mark_price=metrics_data.get('mark_price'),
            index_price=metrics_data.get('index_price')
        )
        
        try:
            self.session.merge(metrics)
            self.session.commit()
            return metrics
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving market metrics: {e}")
            raise
    
    def get_latest_metrics(self, symbol: str) -> Optional[MarketMetrics]:
        return self.session.query(MarketMetrics).filter(
            MarketMetrics.symbol == symbol
        ).order_by(desc(MarketMetrics.timestamp)).first()
    
    # Symbol Info Methods
    def save_symbol_info(self, symbol_data: Dict[str, Any]) -> SymbolInfo:
        symbol_info = SymbolInfo(
            symbol=symbol_data['symbol'],
            base_asset=symbol_data['base_asset'],
            quote_asset=symbol_data['quote_asset'],
            price_precision=symbol_data.get('price_precision'),
            quantity_precision=symbol_data.get('quantity_precision'),
            min_quantity=symbol_data.get('min_quantity'),
            max_quantity=symbol_data.get('max_quantity'),
            step_size=symbol_data.get('step_size'),
            min_notional=symbol_data.get('min_notional'),
            contract_type=symbol_data.get('contract_type'),
            status=symbol_data.get('status'),
            listed_at=symbol_data.get('listed_at')
        )
        
        try:
            existing = self.session.query(SymbolInfo).filter(
                SymbolInfo.symbol == symbol_data['symbol']
            ).first()
            
            if existing:
                for key, value in symbol_data.items():
                    setattr(existing, key, value)
                symbol_info = existing
            else:
                self.session.add(symbol_info)
            
            self.session.commit()
            return symbol_info
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error saving symbol info: {e}")
            raise
    
    def get_symbol_info(self, symbol: str) -> Optional[SymbolInfo]:
        return self.session.query(SymbolInfo).filter(
            SymbolInfo.symbol == symbol
        ).first()
    
    def get_all_active_symbols(self) -> List[SymbolInfo]:
        return self.session.query(SymbolInfo).filter(
            SymbolInfo.status == 'TRADING'
        ).all()
    
    # Utility Methods
    def get_data_time_range(self, symbol: str, table_name: str) -> Dict[str, datetime]:
        if table_name == 'kline':
            result = self.session.query(
                func.min(KlineData.open_time).label('start'),
                func.max(KlineData.open_time).label('end')
            ).filter(KlineData.symbol == symbol).first()
        elif table_name == 'trade':
            result = self.session.query(
                func.min(TradeData.timestamp).label('start'),
                func.max(TradeData.timestamp).label('end')
            ).filter(TradeData.symbol == symbol).first()
        else:
            return {}
        
        if result and result.start and result.end:
            return {'start': result.start, 'end': result.end}
        return {}
    
    def cleanup_old_data(self, days_to_keep: int = 30) -> Dict[str, int]:
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        deleted_counts = {}
        
        try:
            # Clean up old kline data
            deleted_counts['klines'] = self.session.query(KlineData).filter(
                KlineData.created_at < cutoff_date
            ).delete()
            
            # Clean up old orderbook snapshots
            deleted_counts['orderbooks'] = self.session.query(OrderBookSnapshot).filter(
                OrderBookSnapshot.created_at < cutoff_date
            ).delete()
            
            # Clean up old trade data
            deleted_counts['trades'] = self.session.query(TradeData).filter(
                TradeData.created_at < cutoff_date
            ).delete()
            
            # Clean up old indicator values
            deleted_counts['indicators'] = self.session.query(IndicatorValue).filter(
                IndicatorValue.created_at < cutoff_date
            ).delete()
            
            self.session.commit()
            logger.info(f"Cleaned up old data: {deleted_counts}")
            return deleted_counts
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error cleaning up old data: {e}")
            raise