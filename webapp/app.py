#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股主线复盘自动化工具 - Web版 (Flask)
基于 market_review_bot.py 改造
"""

import os
import json
import csv
import io
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from flask import Flask, render_template, request, jsonify, send_from_directory

try:
    import tushare as ts
    import pandas as pd
    TUSHARE_AVAILABLE = True
except ImportError:
    TUSHARE_AVAILABLE = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
HOLDINGS_FILE = os.path.join(DATA_DIR, 'holdings.json')
TRADES_FILE = os.path.join(DATA_DIR, 'trades.json')
ARCHIVE_FILE = os.path.join(DATA_DIR, 'market_review_archive.json')

os.makedirs(DATA_DIR, exist_ok=True)


def format_ts_code(code: str) -> str:
    code = code.strip().upper()
    if not code:
        return code
    if code.endswith('.SH') or code.endswith('.SZ'):
        return code
    if code.startswith('6'):
        return f'{code}.SH'
    elif code.startswith(('0', '3')):
        return f'{code}.SZ'
    elif code.startswith('8') or code.startswith('4'):
        return f'{code}.BJ'
    return code

app = Flask(__name__)


def load_json(filepath: str, default=None):
    if default is None:
        default = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(filepath: str, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_config() -> Dict:
    default = {
        'tushare_token': '',
        'mock_mode': True
    }
    cfg = load_json(CONFIG_FILE, default)
    token = cfg.get('tushare_token', '')
    cfg['mock_mode'] = not token or token == '你的Tushare Pro Token'
    return cfg


def get_holdings() -> List[Dict]:
    default = [
        {"name": "上海瀚讯", "code": "300762.SZ", "sector": "商业航天"}
    ]
    return load_json(HOLDINGS_FILE, default)


def save_holdings(holdings: List[Dict]):
    save_json(HOLDINGS_FILE, holdings)


def get_trades() -> List[Dict]:
    return load_json(TRADES_FILE, [])


def save_trades(trades: List[Dict]):
    save_json(TRADES_FILE, trades)


class TushareMarketReview:
    def __init__(self, token: str):
        self.token = token
        self.pro = ts.pro_api(token)
        self.today = datetime.now().strftime('%Y%m%d')
        self.last_trade_date = self._get_last_trade_date()

    def _get_last_trade_date(self) -> str:
        try:
            today = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
            df = self.pro.daily(ts_code='000001.SZ', start_date=start_date, end_date=today)
            if df is not None and not df.empty:
                return df.iloc[0]['trade_date']
        except Exception:
            pass
        try:
            df = self.pro.trade_cal(exchange='SSE',
                                    start_date=(datetime.now() - timedelta(days=30)).strftime('%Y%m%d'),
                                    end_date=self.today)
            df = df[df['is_open'] == 1]
            return df.iloc[-1]['cal_date'] if not df.empty else self.today
        except Exception as e:
            return self.today

    def get_sector_daily(self, trade_date: str = None):
        if trade_date is None:
            trade_date = self.last_trade_date
        
        try:
            daily_df = self.pro.daily(trade_date=trade_date)
            if daily_df is None or daily_df.empty:
                return None
            
            stocks = self.pro.stock_basic(exchange='', list_status='L', fields='ts_code,industry')
            if stocks is None or stocks.empty:
                return None
            
            df = daily_df.merge(stocks, on='ts_code', how='left')
            df = df[df['industry'].notna() & (df['industry'] != '')]
            
            sector_stats = df.groupby('industry').agg({
                'pct_chg': 'mean',
                'ts_code': 'count',
                'close': 'mean'
            }).reset_index()
            sector_stats = sector_stats.sort_values('pct_chg', ascending=False)
            sector_stats.rename(columns={'industry': 'name', 'pct_chg': 'change', 'ts_code': 'count'}, inplace=True)
            
            return sector_stats
        except Exception:
            try:
                df = self.pro.ths_daily(trade_date=trade_date)
                if df is not None and not df.empty:
                    df = df.sort_values('close', ascending=False)
                return df
            except Exception:
                try:
                    df = self.pro.sw_daily(trade_date=trade_date)
                    if df is not None and not df.empty:
                        df = df.sort_values('close', ascending=False)
                    return df
                except Exception:
                    return None

    def get_limit_list(self, trade_date: str = None):
        if trade_date is None:
            trade_date = self.last_trade_date
        
        try:
            df = self.pro.limit_list_d(trade_date=trade_date)
            return df
        except Exception:
            try:
                df = self.pro.daily(trade_date=trade_date)
                if df is None or df.empty:
                    return None
                df = df[df['pct_chg'] >= 9.8]
                if df.empty:
                    return None
                df['limit'] = df['pct_chg'].apply(lambda x: 1)
                return df
            except Exception:
                return None

    def get_moneyflow_industry(self, trade_date: str = None):
        if trade_date is None:
            trade_date = self.last_trade_date
        try:
            return self.pro.moneyflow_ind_dc(trade_date=trade_date)
        except Exception:
            return None

    def get_moneyflow_industry_history(self, days: int = 7):
        """获取最近N个交易日的行业资金流向数据，返回按日期排序的DataFrame"""
        try:
            end_date = self.last_trade_date
            start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=days * 2 + 5)).strftime('%Y%m%d')
            df = self.pro.moneyflow_ind_dc(start_date=start_date, end_date=end_date)
            if df is None or df.empty:
                return None
            # 按交易日期排序（旧到新）
            df = df.sort_values('trade_date')
            return df
        except Exception:
            return None

    def _analyze_moneyflow_streak(self, days: int = 7, min_streak: int = 3):
        """分析连续净流入的板块，返回排名列表。优先Tushare，降级到akshare，最后模拟数据。"""
        # 第一层：Tushare
        df = self.get_moneyflow_industry_history(days)
        if df is not None and not df.empty:
            return self._parse_moneyflow_df(df, days, min_streak)

        # 第二层：akshare 降级
        ak_result, ak_msg = self._analyze_moneyflow_streak_akshare(min_streak)
        if ak_result:
            return ak_result, ak_msg

        # 第三层：模拟数据
        mock_data = [
            {'name': 'AI算力', 'streak': 5, 'recent_net': 38520.45, 'total_net': 45230.10, 'avg_change': 2.35, 'close': 1258.36, 'days_count': 5},
            {'name': '商业航天', 'streak': 4, 'recent_net': 28150.20, 'total_net': 32100.80, 'avg_change': 1.98, 'close': 1102.45, 'days_count': 5},
            {'name': '半导体', 'streak': 3, 'recent_net': 18650.75, 'total_net': 20340.50, 'avg_change': 1.56, 'close': 986.23, 'days_count': 5},
            {'name': '机器人', 'streak': 3, 'recent_net': 12480.30, 'total_net': 15200.60, 'avg_change': 1.23, 'close': 823.45, 'days_count': 5},
            {'name': '消费电子', 'streak': 3, 'recent_net': 8320.15, 'total_net': 9850.40, 'avg_change': 0.89, 'close': 712.56, 'days_count': 5},
        ]
        return mock_data, "Tushare/akshare均不可用（网络受限或无积分），以下为模拟数据展示"

    def _analyze_moneyflow_streak_akshare(self, min_streak: int = 3):
        """使用akshare获取板块资金流向，作为Tushare的降级方案"""
        try:
            import akshare as ak
            # 获取5日行业板块资金流向排行
            df_5d = ak.stock_sector_fund_flow_rank(indicator="5日", sector_type="行业")
            if df_5d is None or df_5d.empty:
                return None, "akshare获取5日资金流向为空"

            # 同时获取今日资金流向做交叉验证
            df_today = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业")

            results = []
            for _, row in df_5d.iterrows():
                name = str(row.get('板块名称', ''))
                net_5d = float(row.get('主力净流入-净额', 0))
                # 5日净流入必须为正
                if net_5d <= 0:
                    continue

                # 交叉验证：今日是否也为正流入
                today_inflow = True
                if df_today is not None and not df_today.empty:
                    today_row = df_today[df_today['板块名称'] == name]
                    if not today_row.empty:
                        today_net = float(today_row.iloc[0].get('主力净流入-净额', 0))
                        if today_net <= 0:
                            today_inflow = False

                # 如果今日也是正流入，说明至少有连续2日以上，视为连续流入
                # 5日累计为正 + 今日为正，近似认为连续3日以上
                streak = 5 if today_inflow else 3
                if streak < min_streak:
                    continue

                chg = float(row.get('涨跌幅', 0))
                results.append({
                    'name': name,
                    'streak': streak,
                    'recent_net': round(net_5d / 10000, 2),  # 元转万元
                    'total_net': round(net_5d / 10000, 2),
                    'avg_change': round(chg, 2),
                    'close': 0,
                    'days_count': 5
                })

            # 排序：先按连续天数，再按净流入金额
            results.sort(key=lambda x: (x['streak'], x['recent_net']), reverse=True)
            if not results:
                return None, "akshare未找到符合条件的板块"
            return results, ""
        except Exception as e:
            return None, f"akshare获取失败: {e}"

    def _parse_moneyflow_df(self, df, days: int, min_streak: int):
        """解析Tushare资金流向DataFrame"""
        net_col = None
        for col in ['net_amount', 'netflow_amount', 'main_net_amount']:
            if col in df.columns:
                net_col = col
                break
        if net_col is None:
            return [], "资金流向数据字段缺失"

        recent_dates = sorted(df['trade_date'].unique())[-(days if days >= min_streak else min_streak):]
        df_recent = df[df['trade_date'].isin(recent_dates)].copy()
        df_recent['is_inflow'] = df_recent[net_col].astype(float) > 0

        results = []
        name_col = 'name' if 'name' in df_recent.columns else 'industry_name'
        if name_col not in df_recent.columns:
            return [], "行业名称字段缺失"

        for name, group in df_recent.groupby(name_col):
            group = group.sort_values('trade_date')
            if len(group) < min_streak:
                continue

            streak = 0
            for _, row in group.iloc[::-1].iterrows():
                if row['is_inflow']:
                    streak += 1
                else:
                    break

            if streak < min_streak:
                continue

            recent_inflow = group.iloc[-streak:][net_col].astype(float).sum()
            total_net = group[net_col].astype(float).sum()
            pct_col = 'pct_change' if 'pct_change' in group.columns else 'pct_chg'
            avg_chg = float(group[pct_col].astype(float).mean()) if pct_col in group.columns else 0
            close = float(group.iloc[-1].get('close', 0)) if 'close' in group.columns else 0

            results.append({
                'name': str(name),
                'streak': streak,
                'recent_net': round(float(recent_inflow) / 10000, 2),
                'total_net': round(float(total_net) / 10000, 2),
                'avg_change': round(avg_chg, 2),
                'close': round(close, 2),
                'days_count': len(group)
            })

        results.sort(key=lambda x: (x['streak'], x['recent_net']), reverse=True)
        return results, ""

    def daily_review_data(self, holdings: List[Dict]) -> Dict:
        self.last_trade_date = self._get_last_trade_date()
        self.today = datetime.now().strftime('%Y%m%d')
        sector_df = self.get_sector_daily()
        top_sectors = []
        today_top3 = []
        data_warning = ""
        
        if sector_df is not None and not sector_df.empty:
            top10 = sector_df.head(10)
            for _, row in top10.iterrows():
                name = row.get('name', '') or row.get('sw_name', '') or row.get('industry_name', '') or f'板块{len(top_sectors)+1}'
                top_sectors.append({
                    'name': name,
                    'close': float(row.get('close', 0)),
                    'change': float(row.get('change', 0)) if 'change' in row else 0
                })
            today_top3 = [s['name'] for s in top_sectors[:3]]
        else:
            data_warning = "板块数据获取失败，可能是积分不足或接口限制。已切换为模拟数据展示。"
            today_top3 = ["AI算力", "商业航天", "半导体"]
            top_sectors = [
                {'name': 'AI算力', 'close': 1258.36, 'change': 3.25},
                {'name': '商业航天', 'close': 1102.45, 'change': 2.87},
                {'name': '半导体', 'close': 986.23, 'change': 2.15},
                {'name': '新能源', 'close': 876.54, 'change': 1.56},
                {'name': '机器人', 'close': 823.45, 'change': 1.23},
                {'name': '医药生物', 'close': 765.32, 'change': 0.89},
                {'name': '消费电子', 'close': 712.56, 'change': 0.67},
                {'name': '军工', 'close': 689.34, 'change': 0.45},
                {'name': '汽车', 'close': 654.23, 'change': 0.32},
                {'name': '金融', 'close': 623.45, 'change': 0.12},
            ]

        limit_df = self.get_limit_list()
        emotion = self._analyze_emotion(limit_df)
        
        if emotion['limit_up_count'] == 0 and data_warning:
            emotion = {
                "limit_up_count": 45,
                "max_limit_height": 6,
                "break_rate": 15,
                "emotion_state": "正常"
            }

        yesterday_top3 = self._load_yesterday_top3()
        holding_analysis = self._analyze_holdings(holdings, today_top3)

        self._save_today_top3(today_top3)

        changes = []
        if yesterday_top3:
            exited = [s for s in yesterday_top3 if s not in today_top3]
            entered = [s for s in today_top3 if s not in yesterday_top3]
            if exited:
                changes.append(f"退出: {', '.join(exited)}")
            if entered:
                changes.append(f"新进入: {', '.join(entered)}")
            if not exited and not entered:
                changes.append("无变化")
        else:
            changes.append("昨日无存档")
            
        if data_warning and not yesterday_top3:
            yesterday_top3 = ["AI算力", "半导体", "新能源"]
            changes = ["退出: 新能源", "新进入: 商业航天"]

        return {
            'trade_date': self.last_trade_date,
            'yesterday_top3': yesterday_top3,
            'today_top3': today_top3,
            'top_sectors': top_sectors,
            'emotion': emotion,
            'holding_analysis': holding_analysis,
            'changes': changes,
            'mock': False,
            'warning': data_warning
        }

    def _analyze_emotion(self, limit_df) -> Dict:
        result = {
            "limit_up_count": 0,
            "max_limit_height": 0,
            "break_rate": 0,
            "emotion_state": "正常"
        }
        if limit_df is not None and not limit_df.empty:
            result["limit_up_count"] = len(limit_df)
            if 'limit' in limit_df.columns:
                result["max_limit_height"] = int(limit_df['limit'].max())
            result["break_rate"] = 15

        if result["max_limit_height"] >= 5 and result["break_rate"] < 20:
            result["emotion_state"] = "高潮"
        elif result["max_limit_height"] <= 2 or result["break_rate"] > 30:
            result["emotion_state"] = "分歧/低迷"
        else:
            result["emotion_state"] = "正常"
        return result

    def _analyze_holdings(self, holdings: List[Dict], today_top3: List[str]) -> List[Dict]:
        results = []
        for holding in holdings:
            matched = holding.get("sector", "") in today_top3
            results.append({
                "name": holding["name"],
                "code": holding.get("code", ""),
                "sector": holding.get("sector", ""),
                "matched": matched,
                "suggestion": "持有" if matched else "观察/减仓"
            })
        return results

    def weekly_review_data(self, holdings: List[Dict]) -> Dict:
        self.last_trade_date = self._get_last_trade_date()
        self.today = datetime.now().strftime('%Y%m%d')
        end_date = self.last_trade_date
        start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=7)).strftime('%Y%m%d')

        sector_df = self.get_sector_daily(end_date)
        top_sectors = []
        top3 = []
        data_warning = ""
        
        if sector_df is not None and not sector_df.empty:
            for _, row in sector_df.head(10).iterrows():
                name = row.get('name', '') or row.get('sw_name', '') or row.get('industry_name', '') or f'板块{len(top_sectors)+1}'
                top_sectors.append({
                    'name': name,
                    'close': float(row.get('close', 0))
                })
            top3 = [s['name'] for s in top_sectors[:3]]
        else:
            data_warning = "板块数据获取失败，可能是积分不足或接口限制。已切换为模拟数据展示。"
            top_sectors = [
                {'name': 'AI算力', 'close': 1258.36},
                {'name': '商业航天', 'close': 1102.45},
                {'name': '半导体', 'close': 986.23},
                {'name': '新能源', 'close': 876.54},
                {'name': '机器人', 'close': 823.45},
            ]
            top3 = [s['name'] for s in top_sectors[:3]]

        holding_diag = []
        for holding in holdings:
            in_main = holding.get("sector", "") in top3
            action = "持有" if in_main else "减仓50%"
            holding_diag.append({
                "name": holding["name"],
                "code": holding.get("code", ""),
                "sector": holding.get("sector", ""),
                "in_main": in_main,
                "action": action
            })

        sub_sectors = []
        for s in top_sectors[2:5]:
            sub_sectors.append({
                "name": s['name'],
                "stage": "观察"
            })

        evidence = "数据不足" if data_warning else "根据最新板块数据评估"

        # 资金流向分析：连续3日以上净流入的板块排名
        moneyflow_streak, mf_warning = self._analyze_moneyflow_streak(days=7, min_streak=3)

        return {
            'start_date': start_date,
            'end_date': end_date,
            'top3': top3,
            'top_sectors': top_sectors,
            'lifecycle': {"stage": "观察中", "evidence": evidence},
            'sub_sectors': sub_sectors,
            'holding_diag': holding_diag,
            'moneyflow_streak': moneyflow_streak,
            'moneyflow_warning': mf_warning,
            'mock': False,
            'warning': data_warning
        }

    def _load_yesterday_top3(self) -> List[str]:
        data = load_json(ARCHIVE_FILE, {})
        return data.get("last_top3", [])

    def _save_today_top3(self, top3: List[str]):
        data = {
            "date": self.last_trade_date,
            "last_top3": top3
        }
        save_json(ARCHIVE_FILE, data)


class MockMarketReview:
    def __init__(self):
        self.today = datetime.now().strftime('%Y%m%d')
        self.last_trade_date = self.today

    def daily_review_data(self, holdings: List[Dict]) -> Dict:
        today_top3 = ["AI算力", "商业航天", "半导体"]
        top_sectors = [
            {'name': 'AI算力', 'close': 1258.36, 'change': 3.25},
            {'name': '商业航天', 'close': 1102.45, 'change': 2.87},
            {'name': '半导体', 'close': 986.23, 'change': 2.15},
            {'name': '新能源', 'close': 876.54, 'change': 1.56},
            {'name': '机器人', 'close': 823.45, 'change': 1.23},
            {'name': '医药生物', 'close': 765.32, 'change': 0.89},
            {'name': '消费电子', 'close': 712.56, 'change': 0.67},
            {'name': '军工', 'close': 689.34, 'change': 0.45},
            {'name': '汽车', 'close': 654.23, 'change': 0.32},
            {'name': '金融', 'close': 623.45, 'change': 0.12},
        ]

        holding_analysis = []
        for h in holdings:
            matched = h.get("sector", "") in today_top3
            holding_analysis.append({
                "name": h["name"],
                "code": h.get("code", ""),
                "sector": h.get("sector", ""),
                "matched": matched,
                "suggestion": "持有" if matched else "观察/减仓"
            })

        return {
            'trade_date': self.last_trade_date,
            'yesterday_top3': ["AI算力", "半导体", "新能源"],
            'today_top3': today_top3,
            'top_sectors': top_sectors,
            'emotion': {
                "limit_up_count": 45,
                "max_limit_height": 6,
                "break_rate": 15,
                "emotion_state": "正常"
            },
            'holding_analysis': holding_analysis,
            'changes': ["退出: 新能源", "新进入: 商业航天"],
            'mock': True
        }

    def weekly_review_data(self, holdings: List[Dict]) -> Dict:
        end_date = self.today
        start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=7)).strftime('%Y%m%d')
        top3 = ["AI算力", "商业航天", "半导体"]
        top_sectors = [
            {'name': 'AI算力', 'close': 1258.36},
            {'name': '商业航天', 'close': 1102.45},
            {'name': '半导体', 'close': 986.23},
            {'name': '新能源', 'close': 876.54},
            {'name': '机器人', 'close': 823.45},
        ]

        holding_diag = []
        for h in holdings:
            in_main = h.get("sector", "") in top3
            holding_diag.append({
                "name": h["name"],
                "code": h.get("code", ""),
                "sector": h.get("sector", ""),
                "in_main": in_main,
                "action": "持有" if in_main else "减仓50%"
            })

        return {
            'start_date': start_date,
            'end_date': end_date,
            'top3': top3,
            'top_sectors': top_sectors,
            'lifecycle': {"stage": "观察中", "evidence": "数据不足"},
            'sub_sectors': [
                {"name": "新能源", "stage": "观察"},
                {"name": "机器人", "stage": "观察"},
                {"name": "医药生物", "stage": "观察"},
            ],
            'holding_diag': holding_diag,
            'moneyflow_streak': [
                {'name': 'AI算力', 'streak': 5, 'recent_net': 38520.45, 'total_net': 45230.10, 'avg_change': 2.35, 'close': 1258.36, 'days_count': 5},
                {'name': '商业航天', 'streak': 4, 'recent_net': 28150.20, 'total_net': 32100.80, 'avg_change': 1.98, 'close': 1102.45, 'days_count': 5},
                {'name': '半导体', 'streak': 3, 'recent_net': 18650.75, 'total_net': 20340.50, 'avg_change': 1.56, 'close': 986.23, 'days_count': 5},
                {'name': '机器人', 'streak': 3, 'recent_net': 12480.30, 'total_net': 15200.60, 'avg_change': 1.23, 'close': 823.45, 'days_count': 5},
                {'name': '消费电子', 'streak': 3, 'recent_net': 8320.15, 'total_net': 9850.40, 'avg_change': 0.89, 'close': 712.56, 'days_count': 5},
            ],
            'moneyflow_warning': '',
            'mock': True
        }


def get_reviewer():
    cfg = get_config()
    if cfg['mock_mode'] or not TUSHARE_AVAILABLE:
        return MockMarketReview()
    try:
        return TushareMarketReview(cfg['tushare_token'])
    except Exception:
        return MockMarketReview()


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'POST':
        data = request.get_json() or {}
        token = data.get('tushare_token', '').strip()
        cfg = {'tushare_token': token}
        save_json(CONFIG_FILE, cfg)
        return jsonify({'success': True, 'config': get_config()})
    return jsonify(get_config())


@app.route('/api/config/test', methods=['POST'])
def test_token():
    data = request.get_json() or {}
    token = data.get('tushare_token', '').strip()
    if not token:
        return jsonify({'success': False, 'message': 'Token 不能为空'})
    if not TUSHARE_AVAILABLE:
        return jsonify({'success': False, 'message': 'tushare 库未安装'})
    try:
        pro = ts.pro_api(token)
        df = pro.trade_cal(exchange='SSE', start_date='20240101', end_date='20240105')
        if df is not None and not df.empty:
            return jsonify({'success': True, 'message': 'Token 验证成功！'})
        return jsonify({'success': False, 'message': 'Token 验证失败，请检查'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'验证失败: {str(e)}'})


@app.route('/api/holdings', methods=['GET', 'POST', 'DELETE'])
def api_holdings():
    if request.method == 'GET':
        return jsonify(get_holdings())
    elif request.method == 'POST':
        data = request.get_json() or {}
        holdings = data.get('holdings', [])
        save_holdings(holdings)
        return jsonify({'success': True, 'holdings': holdings})
    elif request.method == 'DELETE':
        save_holdings([])
        return jsonify({'success': True, 'holdings': []})


@app.route('/api/holdings/close', methods=['POST'])
def close_holding():
    """平仓：支持部分卖出，记录到交易历史"""
    data = request.get_json() or {}
    idx = data.get('index')
    close_type = data.get('close_type', 'manual')  # profit / loss / manual
    close_price = data.get('close_price', 0)
    close_note = data.get('close_note', '')
    sell_amount = data.get('amount', 0)  # 卖出数量，0表示全部卖出

    if idx is None:
        return jsonify({'success': False, 'message': '缺少持仓索引'})

    holdings = get_holdings()
    if idx < 0 or idx >= len(holdings):
        return jsonify({'success': False, 'message': '持仓索引无效'})

    h = holdings[idx]
    buy_price = float(h.get('cost', 0) or 0)
    total_amount = float(h.get('amount', 0) or 0)
    current_price = float(close_price) if close_price else float(h.get('current_price', 0) or 0)

    # 确定卖出数量：未指定或超过持仓量则全部卖出
    if sell_amount <= 0 or sell_amount >= total_amount:
        sell_amount = total_amount
        is_full = True
    else:
        is_full = False

    # 计算盈亏
    pnl = (current_price - buy_price) * sell_amount if buy_price else 0
    pnl_rate = ((current_price - buy_price) / buy_price * 100) if buy_price else 0

    buy_date = h.get('buy_date', '')
    hold_days = 0
    if buy_date:
        try:
            from datetime import datetime as dt
            d1 = dt.strptime(buy_date, '%Y-%m-%d')
            d2 = dt.now()
            hold_days = (d2 - d1).days
        except Exception:
            pass

    trade = {
        'name': h.get('name', ''),
        'code': h.get('code', ''),
        'sector': h.get('sector', ''),
        'buy_reason': h.get('buy_reason', ''),
        'amount': sell_amount,
        'buy_price': buy_price,
        'close_price': current_price,
        'pnl': round(pnl, 2),
        'pnl_rate': round(pnl_rate, 2),
        'close_type': close_type,
        'close_note': close_note,
        'buy_date': buy_date,
        'close_date': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'hold_days': hold_days
    }

    trades = get_trades()
    trades.insert(0, trade)
    save_trades(trades)

    # 更新或移除持仓
    if is_full:
        holdings.pop(idx)
    else:
        h['amount'] = total_amount - sell_amount
        holdings[idx] = h

    save_holdings(holdings)

    return jsonify({'success': True, 'trade': trade, 'holdings': holdings, 'is_full': is_full})


@app.route('/api/trades', methods=['GET', 'DELETE'])
def api_trades():
    if request.method == 'GET':
        return jsonify(get_trades())
    elif request.method == 'DELETE':
        save_trades([])
        return jsonify({'success': True})


@app.route('/api/trades/stats')
def trades_stats():
    trades = get_trades()
    total = len(trades)
    if total == 0:
        return jsonify({
            'total': 0, 'wins': 0, 'losses': 0,
            'win_rate': 0, 'total_pnl': 0, 'avg_pnl': 0,
            'avg_hold_days': 0, 'best_trade': 0, 'worst_trade': 0
        })

    wins = sum(1 for t in trades if float(t.get('pnl', 0)) > 0)
    losses = sum(1 for t in trades if float(t.get('pnl', 0)) < 0)
    total_pnl = sum(float(t.get('pnl', 0)) for t in trades)
    pnls = [float(t.get('pnl', 0)) for t in trades]
    hold_days_list = [int(t.get('hold_days', 0)) for t in trades if t.get('hold_days')]

    return jsonify({
        'total': total,
        'wins': wins,
        'losses': losses,
        'win_rate': round(wins / total * 100, 1),
        'total_pnl': round(total_pnl, 2),
        'avg_pnl': round(total_pnl / total, 2),
        'avg_hold_days': round(sum(hold_days_list) / len(hold_days_list), 1) if hold_days_list else 0,
        'best_trade': max(pnls),
        'worst_trade': min(pnls)
    })


@app.route('/api/holdings/upload', methods=['POST'])
def upload_holdings():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择文件'})

    filename = file.filename.lower()
    content = file.read().decode('utf-8-sig')
    holdings = []

    try:
        if filename.endswith('.csv'):
            reader = csv.DictReader(io.StringIO(content))
            for row in reader:
                name = row.get('name') or row.get('股票名称') or row.get('名称') or ''
                code = row.get('code') or row.get('股票代码') or row.get('代码') or ''
                sector = row.get('sector') or row.get('所属板块') or row.get('板块') or ''
                amount = row.get('amount') or row.get('数量') or row.get('持仓数量') or 0
                cost = row.get('cost') or row.get('成本') or row.get('盈亏成本') or 0
                current_price = row.get('current_price') or row.get('最新价') or row.get('现价') or 0
                stop_loss = row.get('stop_loss') or row.get('止损价') or 0
                position = row.get('position') or row.get('仓位') or 0
                buy_reason = row.get('buy_reason') or row.get('买入逻辑') or row.get('买入理由') or ''
                if name or code:
                    holdings.append({
                        'name': name.strip(),
                        'code': code.strip(),
                        'sector': sector.strip(),
                        'amount': float(amount) if amount else 0,
                        'cost': float(cost) if cost else 0,
                        'current_price': float(current_price) if current_price else 0,
                        'stop_loss': float(stop_loss) if stop_loss else 0,
                        'position': float(position) if position else 0,
                        'buy_reason': buy_reason.strip(),
                        'available': float(amount) if amount else 0,
                        'value': 0,
                        'pnl': 0
                    })
        elif filename.endswith('.json'):
            data = json.loads(content)
            if isinstance(data, list):
                holdings = data
            elif isinstance(data, dict) and 'holdings' in data:
                holdings = data['holdings']
        else:
            return jsonify({'success': False, 'message': '不支持的文件格式，请上传 CSV 或 JSON 文件'})

        if not holdings:
            return jsonify({'success': False, 'message': '未解析到有效持仓数据'})

        save_holdings(holdings)
        return jsonify({'success': True, 'holdings': holdings, 'count': len(holdings)})
    except Exception as e:
        return jsonify({'success': False, 'message': f'解析失败: {str(e)}'})


@app.route('/api/price')
def get_price():
    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'message': '请提供股票代码'})

    cfg = get_config()
    if cfg['mock_mode']:
        return jsonify({'success': False, 'message': '模拟模式下无法获取实时价格'})

    code = format_ts_code(code)
    code_pure = code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')

    try:
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        stock_row = df[df['代码'] == code_pure]
        if not stock_row.empty:
            price = float(stock_row.iloc[0]['最新价'])
            return jsonify({
                'success': True,
                'price': price,
                'source': 'realtime',
                'source_name': '实时行情(东方财富)',
                'update_time': datetime.now().strftime('%H:%M:%S')
            })
    except Exception:
        pass

    try:
        import requests
        if code.endswith('.SH'):
            sina_code = 'sh' + code_pure
        elif code.endswith('.SZ'):
            sina_code = 'sz' + code_pure
        else:
            sina_code = 'bj' + code_pure

        url = f'https://hq.sinajs.cn/list={sina_code}'
        headers = {'Referer': 'https://finance.sina.com.cn'}
        r = requests.get(url, headers=headers, timeout=5)
        r.encoding = 'gbk'
        if r.status_code == 200 and '="' in r.text:
            data_str = r.text.split('"')[1]
            fields = data_str.split(',')
            if len(fields) >= 4:
                price = float(fields[3])
                if price > 0:
                    return jsonify({
                        'success': True,
                        'price': price,
                        'source': 'realtime',
                        'source_name': '实时行情(新浪)',
                        'update_time': datetime.now().strftime('%H:%M:%S')
                    })
    except Exception:
        pass

    try:
        if TUSHARE_AVAILABLE:
            pro = ts.pro_api(cfg['tushare_token'])
            df = pro.daily(ts_code=code)
            if df is not None and not df.empty:
                trade_date = df.iloc[0]['trade_date']
                return jsonify({
                    'success': True,
                    'price': float(df.iloc[0]['close']),
                    'source': 'daily',
                    'source_name': f'日线({trade_date[4:6]}/{trade_date[6:8]})',
                    'update_time': trade_date
                })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

    return jsonify({'success': False, 'message': '未找到该股票数据'})


@app.route('/api/stock/info')
def get_stock_info():
    code = request.args.get('code', '').strip()
    if not code:
        return jsonify({'success': False, 'message': '请提供股票代码'})

    cfg = get_config()
    if cfg['mock_mode']:
        return jsonify({'success': False, 'message': '模拟模式下无法获取实时价格'})

    try:
        code = format_ts_code(code)
        code_pure = code.replace('.SH', '').replace('.SZ', '').replace('.BJ', '')

        # 获取名称和行业（从 Tushare）
        name = ''
        industry = ''
        if TUSHARE_AVAILABLE:
            pro = ts.pro_api(cfg['tushare_token'])
            stocks = pro.stock_basic(ts_code=code, fields='ts_code,name,industry')
            if stocks is not None and not stocks.empty:
                name = stocks.iloc[0]['name']
                industry = stocks.iloc[0]['industry'] or ''

        # 获取实时价格（优先 akshare）
        price = None
        source = 'daily'
        try:
            import akshare as ak
            df = ak.stock_zh_a_spot_em()
            stock_row = df[df['代码'] == code_pure]
            if not stock_row.empty:
                price = float(stock_row.iloc[0]['最新价'])
                source = 'realtime'
        except Exception:
            pass

        # 回退到 Tushare 日线
        if price is None and TUSHARE_AVAILABLE:
            pro = ts.pro_api(cfg['tushare_token'])
            df = pro.daily(ts_code=code)
            if df is not None and not df.empty:
                price = float(df.iloc[0]['close'])

        if price is None:
            return jsonify({'success': False, 'message': '未找到该股票数据'})

        return jsonify({
            'success': True,
            'code': code,
            'name': name,
            'price': price,
            'industry': industry,
            'source': source
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/holdings/ocr', methods=['POST'])
def ocr_holdings():
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': '没有上传图片'})
    file = request.files['image']
    if file.filename == '':
        return jsonify({'success': False, 'message': '未选择图片'})
    
    try:
        import re
        from PIL import Image
        import pytesseract

        img_path = os.path.join(DATA_DIR, 'temp_ocr.png')
        file.save(img_path)

        img = Image.open(img_path)
        # 转为灰度提高识别率
        img_gray = img.convert('L')

        # 使用表格模式识别（psm 6 = 假设为统一的文本块）
        text = pytesseract.image_to_string(img_gray, lang='chi_sim+eng', config='--psm 6')

        # 用TSV模式获取每个文字的坐标位置
        try:
            data = pytesseract.image_to_data(img_gray, lang='chi_sim+eng', config='--psm 6', output_type=pytesseract.Output.DICT)
        except:
            data = None

        lines = text.split('\n')
        holdings = []

        # 找到表头行，确定列位置
        header_line = None
        for line in lines:
            if '证券代码' in line or ('代码' in line and '名称' in line):
                header_line = line
                break

        # 改进策略：按行解析，每行包含一条持仓数据
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 跳过表头和合计行
            if any(kw in line for kw in ['证券代码', '证券名称', '持仓合计', '合计', '证券市值', '浮动盈亏', '当日盈亏', '最新价']):
                continue

            # 提取所有6位数字
            codes = re.findall(r'\b(\d{6})\b', line)
            if not codes:
                continue

            code = codes[0]

            # 股票代码通常以特定数字开头
            # 沪市: 6开头; 深市: 0/3开头; 北交所: 8/4开头
            if not (code[0] in ['0', '3', '6', '8', '4']):
                continue

            # 提取中文名称（2-8个中文字符）
            names = re.findall(r'[\u4e00-\u9fa5]{2,8}', line)
            if not names:
                continue

            # 过滤明显的非股票名称
            blacklist = ['证券代码', '证券名称', '持仓', '股票', '代码', '名称', '数量', '最新价',
                         '成本', '仓位', '盈亏', '可用', '比例', '当日', '浮动', '市值', '股份']
            valid_names = [n for n in names if n not in blacklist]
            if not valid_names:
                continue

            name = valid_names[0]

            # 提取所有数字（除代码外的）
            all_nums = re.findall(r'\b(\d+(?:\.\d+)?)\b', line)
            nums = []
            for n in all_nums:
                n_clean = n.replace(',', '')
                try:
                    nums.append(float(n_clean))
                except:
                    pass

            # 找到代码在所有数字中的位置
            try:
                code_pos = all_nums.index(code)
            except ValueError:
                code_pos = 0

            # 数量 = 代码之后第一个大整数（>=100）
            amount = 0
            for i in range(code_pos + 1, len(all_nums)):
                n_val = float(all_nums[i].replace(',', ''))
                if n_val >= 100 and n_val == int(n_val):  # 整数且>=100
                    amount = int(n_val)
                    break

            # 补全交易所后缀
            if code.startswith('6'):
                full_code = f'{code}.SH'
            elif code.startswith(('0', '3')):
                full_code = f'{code}.SZ'
            elif code.startswith(('8', '4')):
                full_code = f'{code}.BJ'
            else:
                full_code = code

            holdings.append({
                'name': name,
                'code': full_code,
                'amount': amount,
                'available': amount,
                'position': 0,
                'cost': 0,
                'current_price': 0,
                'value': 0,
                'pnl': 0,
                'stop_loss': 0,
                'buy_reason': '',
                'sector': ''
            })

        # 去重（按代码）
        seen = set()
        unique_holdings = []
        for h in holdings:
            if h['code'] not in seen:
                seen.add(h['code'])
                unique_holdings.append(h)

        os.remove(img_path)

        if unique_holdings:
            return jsonify({'success': True, 'holdings': unique_holdings, 'raw_text': text[:500]})
        return jsonify({'success': False, 'message': '未能识别持仓信息，请尝试更清晰的图片', 'raw_text': text[:500]})
    except ImportError:
        return jsonify({'success': False, 'message': 'OCR功能需要安装pytesseract和Pillow库'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'识别失败: {str(e)}'})


@app.route('/api/review/daily')
def daily_review():
    reviewer = get_reviewer()
    holdings = get_holdings()
    try:
        data = reviewer.daily_review_data(holdings)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/review/weekly')
def weekly_review():
    reviewer = get_reviewer()
    holdings = get_holdings()
    try:
        data = reviewer.weekly_review_data(holdings)
        return jsonify({'success': True, 'data': data})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/api/status')
def api_status():
    cfg = get_config()
    return jsonify({
        'mock_mode': cfg['mock_mode'],
        'tushare_available': TUSHARE_AVAILABLE,
        'token_configured': not cfg['mock_mode'],
        'holdings_count': len(get_holdings())
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
