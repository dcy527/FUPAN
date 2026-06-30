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
ARCHIVE_FILE = os.path.join(DATA_DIR, 'market_review_archive.json')

os.makedirs(DATA_DIR, exist_ok=True)

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


class TushareMarketReview:
    def __init__(self, token: str):
        self.token = token
        self.pro = ts.pro_api(token)
        self.today = datetime.now().strftime('%Y%m%d')
        self.last_trade_date = self._get_last_trade_date()

    def _get_last_trade_date(self) -> str:
        try:
            df = self.pro.trade_cal(exchange='SSE',
                                    start_date=(datetime.now() - timedelta(days=10)).strftime('%Y%m%d'),
                                    end_date=self.today)
            df = df[df['is_open'] == 1]
            return df.iloc[-1]['cal_date'] if not df.empty else self.today
        except Exception as e:
            return self.today

    def get_sector_daily(self, trade_date: str = None):
        if trade_date is None:
            trade_date = self.last_trade_date
        try:
            df = self.pro.ths_daily(trade_date=trade_date)
            if df is not None and not df.empty:
                df = df.sort_values('close', ascending=False)
            return df
        except Exception:
            return None

    def get_limit_list(self, trade_date: str = None):
        if trade_date is None:
            trade_date = self.last_trade_date
        try:
            return self.pro.limit_list_d(trade_date=trade_date)
        except Exception:
            return None

    def get_moneyflow_industry(self, trade_date: str = None):
        if trade_date is None:
            trade_date = self.last_trade_date
        try:
            return self.pro.moneyflow_ind_dc(trade_date=trade_date)
        except Exception:
            return None

    def daily_review_data(self, holdings: List[Dict]) -> Dict:
        sector_df = self.get_sector_daily()
        top_sectors = []
        today_top3 = []
        if sector_df is not None and not sector_df.empty:
            top10 = sector_df.head(10)
            for _, row in top10.iterrows():
                top_sectors.append({
                    'name': row.get('name', ''),
                    'close': float(row.get('close', 0)),
                    'change': float(row.get('change', 0)) if 'change' in row else 0
                })
            today_top3 = [s['name'] for s in top_sectors[:3]]

        limit_df = self.get_limit_list()
        emotion = self._analyze_emotion(limit_df)

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

        return {
            'trade_date': self.last_trade_date,
            'yesterday_top3': yesterday_top3,
            'today_top3': today_top3,
            'top_sectors': top_sectors,
            'emotion': emotion,
            'holding_analysis': holding_analysis,
            'changes': changes,
            'mock': False
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
        end_date = self.last_trade_date
        start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=7)).strftime('%Y%m%d')

        sector_df = self.get_sector_daily(end_date)
        top_sectors = []
        top3 = []
        if sector_df is not None and not sector_df.empty:
            for _, row in sector_df.head(10).iterrows():
                top_sectors.append({
                    'name': row.get('name', ''),
                    'close': float(row.get('close', 0))
                })
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

        return {
            'start_date': start_date,
            'end_date': end_date,
            'top3': top3,
            'top_sectors': top_sectors,
            'lifecycle': {"stage": "观察中", "evidence": "数据不足"},
            'sub_sectors': sub_sectors,
            'holding_diag': holding_diag,
            'mock': False
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
                if name or code:
                    holdings.append({
                        'name': name.strip(),
                        'code': code.strip(),
                        'sector': sector.strip()
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
