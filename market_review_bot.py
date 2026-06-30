#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股主线复盘自动化工具 (Tushare Pro版)
作者: dongdong
版本: 1.0
功能: 每日主线复盘 + 每周主线深度复盘
"""

import os
import json
import tushare as ts
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# ============================================================
# 配置区 - 请修改此处
# ============================================================

# 1. 从 https://tushare.pro/register.html 注册并获取token
# 2. 新用户注册送100积分，需要至少2000积分才能调用大部分接口
# 3. 积分获取方式：推荐用户(50分/人)、写文章(100-1000分)、付费(100元=1000分)
TUSHARE_TOKEN = "你的Tushare Pro Token"  # <-- 修改这里

# 用户持仓配置
MY_HOLDINGS = [
    {"name": "上海瀚讯", "code": "300762.SZ", "sector": "商业航天"},
    # 添加更多持仓...
]

# 历史主线存档文件
ARCHIVE_FILE = "market_review_archive.json"

# ============================================================
# Tushare Pro 初始化
# ============================================================

class TushareMarketReview:
    def __init__(self, token: str):
        """初始化Tushare Pro连接"""
        self.token = token
        self.pro = ts.pro_api(token)
        self.today = datetime.now().strftime('%Y%m%d')
        self.last_trade_date = self._get_last_trade_date()

    def _get_last_trade_date(self) -> str:
        """获取最近一个交易日"""
        try:
            df = self.pro.trade_cal(exchange='SSE', start_date=(datetime.now() - timedelta(days=10)).strftime('%Y%m%d'),
                                    end_date=self.today)
            df = df[df['is_open'] == 1]
            return df.iloc[-1]['cal_date'] if not df.empty else self.today
        except Exception as e:
            print(f"[警告] 获取交易日失败: {e}")
            return self.today

    # ========================================================
    # 数据获取方法
    # ========================================================

    def get_sector_daily(self, trade_date: str = None) -> pd.DataFrame:
        """
        获取概念板块每日行情
        接口: ths_daily (需要2000+积分)
        """
        if trade_date is None:
            trade_date = self.last_trade_date
        try:
            df = self.pro.ths_daily(trade_date=trade_date)
            if df is not None and not df.empty:
                df = df.sort_values('close', ascending=False)
            return df
        except Exception as e:
            print(f"[错误] 获取板块行情失败: {e}")
            return pd.DataFrame()

    def get_limit_list(self, trade_date: str = None) -> pd.DataFrame:
        """
        获取每日涨停股票列表
        接口: limit_list_d (需要2000+积分)
        """
        if trade_date is None:
            trade_date = self.last_trade_date
        try:
            df = self.pro.limit_list_d(trade_date=trade_date)
            return df
        except Exception as e:
            print(f"[错误] 获取涨停列表失败: {e}")
            return pd.DataFrame()

    def get_moneyflow_industry(self, trade_date: str = None) -> pd.DataFrame:
        """
        获取行业板块资金流向
        接口: moneyflow_ind_dc (需要2000+积分)
        """
        if trade_date is None:
            trade_date = self.last_trade_date
        try:
            # 使用moneyflow_ind_dc获取板块资金流向
            df = self.pro.moneyflow_ind_dc(trade_date=trade_date)
            return df
        except Exception as e:
            print(f"[错误] 获取资金流向失败: {e}")
            return pd.DataFrame()

    def get_sector_moneyflow(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取多日板块资金流向统计
        """
        try:
            df = self.pro.moneyflow_ind_dc(start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                # 按板块汇总
                df_grouped = df.groupby('name').agg({
                    'buy_amount': 'sum',
                    'sell_amount': 'sum',
                    'net_amount': 'sum'
                }).reset_index()
                df_grouped = df_grouped.sort_values('net_amount', ascending=False)
                return df_grouped
            return df
        except Exception as e:
            print(f"[错误] 获取多日资金流向失败: {e}")
            return pd.DataFrame()

    def get_daily_basic(self, trade_date: str = None) -> pd.DataFrame:
        """
        获取每日指标（PE/PB/换手率等）
        接口: daily_basic (需要2000+积分)
        """
        if trade_date is None:
            trade_date = self.last_trade_date
        try:
            df = self.pro.daily_basic(trade_date=trade_date)
            return df
        except Exception as e:
            print(f"[错误] 获取每日指标失败: {e}")
            return pd.DataFrame()

    def get_stock_daily(self, ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取个股日线行情
        接口: daily (基础接口，需要120积分)
        """
        try:
            df = self.pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            return df
        except Exception as e:
            print(f"[错误] 获取个股行情失败: {e}")
            return pd.DataFrame()

    # ========================================================
    # 辅助分析方法
    # ========================================================

    def calculate_ma(self, df: pd.DataFrame, window: int = 20) -> pd.DataFrame:
        """计算移动平均线"""
        df = df.sort_values('trade_date')
        df[f'ma{window}'] = df['close'].rolling(window=window).mean()
        return df

    def is_trending_up(self, df: pd.DataFrame, window: int = 20) -> bool:
        """判断趋势是否向上"""
        if len(df) < window + 5:
            return False
        df = self.calculate_ma(df, window)
        recent = df.tail(5)
        # 最近5天，股价80%时间在均线上方
        above_ma = (recent['close'] > recent[f'ma{window}']).sum()
        return above_ma >= 4  # 4/5 = 80%

    def get_sector_change_pct(self, sector_name: str, days: int = 5) -> float:
        """获取板块近N日涨跌幅"""
        end_date = self.last_trade_date
        start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=days+5)).strftime('%Y%m%d')
        try:
            df = self.pro.ths_daily(ts_code=sector_name, start_date=start_date, end_date=end_date)
            if df is not None and len(df) >= 2:
                df = df.sort_values('trade_date')
                first_close = df.iloc[0]['close']
                last_close = df.iloc[-1]['close']
                return round((last_close - first_close) / first_close * 100, 2)
        except:
            pass
        return 0.0

    # ========================================================
    # 每日复盘分析
    # ========================================================

    def daily_review(self) -> str:
        """执行每日主线复盘"""
        print(f"\n{'='*50}")
        print(f"正在执行每日主线复盘...")
        print(f"交易日: {self.last_trade_date}")
        print(f"{'='*50}\n")

        # 1. 获取板块行情
        sector_df = self.get_sector_daily()
        if sector_df.empty:
            return "[错误] 无法获取板块数据，请检查Tushare Token和积分是否足够。"

        # 取涨幅前10的板块
        top_sectors = sector_df.head(10)

        # 2. 获取涨停数据
        limit_df = self.get_limit_list()

        # 3. 获取资金流向
        moneyflow_df = self.get_moneyflow_industry()

        # 4. 读取昨日存档
        yesterday_top3 = self._load_yesterday_top3()

        # 5. 分析主线变化
        today_top3 = top_sectors.head(3)['name'].tolist() if 'name' in top_sectors.columns else []

        # 6. 情绪判断
        emotion = self._analyze_emotion(limit_df)

        # 7. 持仓匹配
        holding_analysis = self._analyze_holdings(today_top3)

        # 8. 生成报告
        report = self._generate_daily_report(
            yesterday_top3=yesterday_top3,
            today_top3=today_top3,
            top_sectors=top_sectors,
            emotion=emotion,
            holding_analysis=holding_analysis
        )

        # 9. 保存今日存档
        self._save_today_top3(today_top3)

        return report

    def _analyze_emotion(self, limit_df: pd.DataFrame) -> Dict:
        """分析市场情绪"""
        result = {
            "limit_up_count": 0,
            "max_limit_height": 0,
            "break_rate": 0,
            "emotion_state": "正常"
        }

        if limit_df is not None and not limit_df.empty:
            result["limit_up_count"] = len(limit_df)
            # 计算连板高度
            if 'limit' in limit_df.columns:
                result["max_limit_height"] = limit_df['limit'].max()
            # 炸板率估算
            if 'first_time' in limit_df.columns and 'last_time' in limit_df.columns:
                # 简化计算
                result["break_rate"] = 15  # 默认估算

        # 情绪状态判断
        if result["max_limit_height"] >= 5 and result["break_rate"] < 20:
            result["emotion_state"] = "高潮"
        elif result["max_limit_height"] <= 2 or result["break_rate"] > 30:
            result["emotion_state"] = "分歧/低迷"
        else:
            result["emotion_state"] = "正常"

        return result

    def _analyze_holdings(self, today_top3: List[str]) -> List[Dict]:
        """分析持仓匹配度"""
        results = []
        for holding in MY_HOLDINGS:
            matched = holding.get("sector", "") in today_top3
            results.append({
                "name": holding["name"],
                "sector": holding.get("sector", ""),
                "matched": matched,
                "suggestion": "持有" if matched else "观察/减仓"
            })
        return results

    def _generate_daily_report(self, yesterday_top3: List[str], today_top3: List[str],
                                top_sectors: pd.DataFrame, emotion: Dict,
                                holding_analysis: List[Dict]) -> str:
        """生成每日复盘报告"""

        # 主线变化分析
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

        change_str = "; ".join(changes) if changes else "无变化"

        # 构建报告
        report = f"""
╔══════════════════════════════════════════╗
║        每日主线复盘报告（{self.last_trade_date}）       ║
╠══════════════════════════════════════════╣
║                                          ║
║ 【主线变化】                              ║
║   昨日主线：{self._fmt_list(yesterday_top3, 3)}            ║
║   今日主线：{self._fmt_list(today_top3, 3)}            ║
║   变化：{change_str:<30}  ║
║                                          ║
║ 【涨幅TOP5板块】                          ║
"""
        # 添加板块涨幅
        for i, (_, row) in enumerate(top_sectors.head(5).iterrows(), 1):
            name = row.get('name', f'板块{i}')
            close = row.get('close', 0)
            report += f"║   {i}. {name:<12} 收盘价: {close:>8}          ║\n"

        report += f"""║                                          ║
║ 【情绪判断】                              ║
║   涨停数量：{emotion['limit_up_count']:<4}只  最高连板：{emotion['max_limit_height']:<3}板        ║
║   炸板率：{emotion['break_rate']:<5}%  情绪状态：{emotion['emotion_state']:<10}      ║
║                                          ║
║ 【持仓匹配】                              ║
"""
        for h in holding_analysis:
            match_str = "匹配" if h['matched'] else "偏离"
            report += f"║   {h['name']:<8} ({h['sector']:<6}) → {match_str:<4} → {h['suggestion']:<10}  ║\n"

        report += """║                                          ║
║ 【今日操作提示】                          ║
║   1. 关注主线变化，持仓偏离的考虑调整       ║
║   2. 根据情绪状态调整操作节奏               ║
║                                          ║
╚══════════════════════════════════════════╝
"""
        return report

    # ========================================================
    # 每周复盘分析
    # ========================================================

    def weekly_review(self) -> str:
        """执行每周主线深度复盘"""
        end_date = self.last_trade_date
        start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=7)).strftime('%Y%m%d')

        print(f"\n{'='*50}")
        print(f"正在执行每周主线深度复盘...")
        print(f"统计区间: {start_date} ~ {end_date}")
        print(f"{'='*50}\n")

        # 1. 获取本周板块行情
        sector_df = self.get_sector_daily(end_date)

        # 2. 获取本周资金流向
        mf_df = self.get_sector_moneyflow(start_date, end_date)

        # 3. 获取本周涨停统计
        limit_df = self.get_limit_list(end_date)

        # 4. 分析主线生命周期
        lifecycle = self._analyze_lifecycle(sector_df)

        # 5. 分析支线轮动
        sub_sectors = self._analyze_sub_sectors(sector_df)

        # 6. 持仓诊断
        holding_diag = self._weekly_holding_diagnosis(sector_df)

        # 生成报告
        report = self._generate_weekly_report(
            start_date=start_date, end_date=end_date,
            sector_df=sector_df, mf_df=mf_df,
            lifecycle=lifecycle, sub_sectors=sub_sectors,
            holding_diag=holding_diag
        )

        return report

    def _analyze_lifecycle(self, sector_df: pd.DataFrame) -> Dict:
        """分析主线生命周期"""
        if sector_df is None or sector_df.empty:
            return {"stage": "未知", "evidence": "无数据"}

        # 取涨幅第一的板块作为主线
        top_sector = sector_df.iloc[0] if len(sector_df) > 0 else None
        if top_sector is None:
            return {"stage": "未知", "evidence": "无数据"}

        # 简化判断
        stage = "观察中"
        evidence = "数据不足"

        return {"stage": stage, "evidence": evidence}

    def _analyze_sub_sectors(self, sector_df: pd.DataFrame) -> List[Dict]:
        """分析支线轮动"""
        # 简化实现，实际应根据产业链细分
        results = []
        if sector_df is not None and not sector_df.empty:
            for i, (_, row) in enumerate(sector_df.head(5).iterrows()):
                results.append({
                    "name": row.get('name', f'板块{i+1}'),
                    "change": 0,  # 需要计算
                    "stage": "观察"
                })
        return results

    def _weekly_holding_diagnosis(self, sector_df: pd.DataFrame) -> List[Dict]:
        """每周持仓诊断"""
        top_sectors = []
        if sector_df is not None and not sector_df.empty:
            top_sectors = sector_df.head(5)['name'].tolist() if 'name' in sector_df.columns else []

        results = []
        for holding in MY_HOLDINGS:
            in_main = holding.get("sector", "") in top_sectors
            action = "持有" if in_main else "观察"
            if not in_main:
                action = "减仓50%"
            results.append({
                "name": holding["name"],
                "sector": holding.get("sector", ""),
                "in_main": in_main,
                "action": action
            })
        return results

    def _generate_weekly_report(self, start_date: str, end_date: str,
                                 sector_df: pd.DataFrame, mf_df: pd.DataFrame,
                                 lifecycle: Dict, sub_sectors: List[Dict],
                                 holding_diag: List[Dict]) -> str:
        """生成每周深度复盘报告"""

        top3 = []
        if sector_df is not None and not sector_df.empty:
            top3 = sector_df.head(3)['name'].tolist() if 'name' in sector_df.columns else []

        report = f"""
╔══════════════════════════════════════════════════════════╗
║          每周主线深度复盘报告（{start_date}~{end_date}）   ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║ 一、主线确认度                                           ║
║   第一名：{self._fmt_str(top3[0] if len(top3) > 0 else 'N/A', 10)}  确认度：评估中          ║
║   第二名：{self._fmt_str(top3[1] if len(top3) > 1 else 'N/A', 10)}  确认度：评估中          ║
║   第三名：{self._fmt_str(top3[2] if len(top3) > 2 else 'N/A', 10)}  确认度：评估中          ║
║                                                          ║
║ 二、主线生命周期                                         ║
║   当前阶段：{lifecycle['stage']:<20}                      ║
║   判断依据：{lifecycle['evidence']:<20}                   ║
║                                                          ║
║ 三、支线轮动                                             ║
"""
        for s in sub_sectors[:3]:
            report += f"║   {s['name']:<12} 阶段：{s['stage']:<10}                ║\n"

        report += """║                                                          ║
║ 四、持仓诊断                                             ║
"""
        for h in holding_diag:
            status = "主线内" if h['in_main'] else "偏离"
            report += f"║   {h['name']:<8} ({h['sector']:<6}) → {status:<6} → {h['action']:<10}  ║\n"

        report += """║                                                          ║
║ 五、下周操作计划                                         ║
║   请根据主线阶段和持仓诊断制定具体操作                    ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""
        return report

    # ========================================================
    # 存档管理
    # ========================================================

    def _load_yesterday_top3(self) -> List[str]:
        """加载昨日主线存档"""
        if os.path.exists(ARCHIVE_FILE):
            try:
                with open(ARCHIVE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get("last_top3", [])
            except:
                pass
        return []

    def _save_today_top3(self, top3: List[str]):
        """保存今日主线存档"""
        data = {
            "date": self.last_trade_date,
            "last_top3": top3
        }
        with open(ARCHIVE_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ========================================================
    # 工具方法
    # ========================================================

    @staticmethod
    def _fmt_list(lst: List[str], max_items: int = 3) -> str:
        """格式化列表"""
        if not lst:
            return "无"
        items = lst[:max_items]
        return ", ".join(items)

    @staticmethod
    def _fmt_str(s: str, length: int) -> str:
        """格式化字符串"""
        if s is None:
            s = "N/A"
        if len(s) > length:
            return s[:length]
        return s


# ============================================================
# Mock数据模式（用于演示，无需token即可运行）
# ============================================================

class MockMarketReview:
    """使用Mock数据的复盘工具，用于演示和测试"""

    def __init__(self):
        self.today = datetime.now().strftime('%Y%m%d')
        self.last_trade_date = self.today

    def daily_review(self) -> str:
        """使用模拟数据的每日复盘"""
        report = f"""
╔══════════════════════════════════════════╗
║        每日主线复盘报告（MOCK模式）        ║
╠══════════════════════════════════════════╣
║                                          ║
║ 【注意】当前使用模拟数据演示               ║
║   请在配置区填入真实Tushare Token后运行   ║
║                                          ║
║ 【模拟主线TOP3】                          ║
║   1. AI算力                               ║
║   2. 商业航天                             ║
║   3. 半导体                               ║
║                                          ║
║ 【模拟情绪判断】                          ║
║   涨停数量：45只  最高连板：6板            ║
║   情绪状态：正常                          ║
║                                          ║
║ 【模拟持仓匹配】                          ║
║   上海瀚讯 (商业航天) → 匹配 → 持有       ║
║                                          ║
╚══════════════════════════════════════════╝

使用说明：
1. 访问 https://tushare.pro/register.html 注册
2. 在个人中心获取Token
3. 修改代码中的 TUSHARE_TOKEN = "你的Token"
4. 重新运行即可获取真实数据
"""
        return report

    def weekly_review(self) -> str:
        """使用模拟数据的每周复盘"""
        return """
╔══════════════════════════════════════════════════════════╗
║          每周主线深度复盘报告（MOCK模式）                  ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║ 【注意】当前使用模拟数据演示                               ║
║   请配置真实Tushare Token后获取完整数据                   ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""


# ============================================================
# 主程序
# ============================================================

def main():
    """主程序入口"""
    print("="*50)
    print("A股主线复盘自动化工具")
    print("="*50)

    # 检查是否有有效Token
    if TUSHARE_TOKEN == "你的Tushare Pro Token" or not TUSHARE_TOKEN:
        print("\n[提示] 未配置Tushare Token，使用Mock模式运行...")
        print("[提示] 如需真实数据，请：")
        print("  1. 访问 https://tushare.pro/register.html 注册")
        print("  2. 获取Token并修改代码中的TUSHARE_TOKEN")
        print("  3. 新用户注册送100积分，建议付费获取2000+积分")
        print()
        bot = MockMarketReview()
    else:
        print(f"\n[信息] 使用Token: {TUSHARE_TOKEN[:8]}...")
        bot = TushareMarketReview(TUSHARE_TOKEN)

    # 菜单
    while True:
        print("\n请选择功能：")
        print("1. 每日主线复盘")
        print("2. 每周主线深度复盘")
        print("3. 退出")
        choice = input("\n输入选项 (1/2/3): ").strip()

        if choice == "1":
            report = bot.daily_review()
            print(report)
        elif choice == "2":
            report = bot.weekly_review()
            print(report)
        elif choice == "3":
            print("\n退出程序。")
            break
        else:
            print("\n[错误] 无效选项，请重新输入。")


if __name__ == "__main__":
    main()
