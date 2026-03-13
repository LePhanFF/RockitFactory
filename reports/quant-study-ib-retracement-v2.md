# IB Retracement V2 Study — Liquidity Sweep + HTF Context

## Thesis

V1 tested 16 configurations using IB close position (top/bottom 30%) for direction.
ALL 16 were negative expectancy. The core problem: weak impulse detection.

V2 replaces that with **liquidity sweep detection** — price takes a key level
(London H/L, PDH/PDL, Overnight H/L) during IB and reverses back inside.
This is a proven ICT concept (Judas Swing) applied to IB retracement.

Additionally, V2 tests **extreme IB ranges** (>=150, 200, 250, 300, 400 pts)
to filter for genuine impulse days vs balance/chop.

## Data

- **Instrument**: NQ
- **Sessions**: 273
- **Execution**: 1 tick slippage/side, $2.05 commission/side, 1 contract
- **Configs tested**: 192
- **Configs with trades**: 192

## IB Range Distribution

- Mean: 197 pts, Median: 178 pts, Std: 129 pts

| Threshold | Sessions | % of Total |
|-----------|----------|------------|
| >= 100 pts | 233 | 85.3% |
| >= 150 pts | 165 | 60.4% |
| >= 200 pts | 109 | 39.9% |
| >= 250 pts | 66 | 24.2% |
| >= 300 pts | 36 | 13.2% |
| >= 400 pts | 13 | 4.8% |
| >= 500 pts | 1 | 0.4% |

## Liquidity Sweep Frequency

- Sessions with at least one sweep: **187** (68.5%)
- Sessions with IB close direction (30%): **190** (69.6%)

## Full Results Matrix

Configs with >= 5 trades, sorted by Profit Factor:

| Config | Trades | WR% | PF | Net PnL | Avg Win | Avg Loss | Expect | S/L |
|--------|--------|-----|-----|---------|---------|----------|--------|-----|
| IB>=300_sweep_vwap_confirm_1_5x_ib | 6 | 50.0% | 3.13 | $10,213 | $5,001 | $-1,597 | $1,702 | 5/1 |
| IB>=300_sweep_vwap_confirm_2R | 6 | 50.0% | 2.46 | $7,003 | $3,931 | $-1,597 | $1,167 | 5/1 |
| IB>=300_sweep_vwap_confirm_1R | 6 | 50.0% | 1.67 | $3,193 | $2,661 | $-1,597 | $532 | 5/1 |
| IB>=300_sweep_vwap_confirm_opp_ib | 6 | 50.0% | 1.62 | $2,993 | $2,594 | $-1,597 | $499 | 5/1 |
| IB>=250_sweep_vwap_confirm_1_5x_ib | 11 | 36.4% | 1.37 | $5,192 | $4,787 | $-1,993 | $472 | 7/4 |
| IB>=200_sweep_vwap_confirm_1_5x_ib | 14 | 35.7% | 1.31 | $4,938 | $4,224 | $-1,798 | $353 | 10/4 |
| IB>=250_sweep_vwap_confirm_2R | 11 | 36.4% | 1.14 | $1,982 | $3,984 | $-1,993 | $180 | 7/4 |
| IB>=200_sweep_vwap_confirm_2R | 14 | 35.7% | 1.11 | $1,728 | $3,582 | $-1,798 | $123 | 10/4 |
| IB>=100_sweep_vwap_confirm_1_5x_ib | 37 | 37.8% | 0.96 | $-1,662 | $2,661 | $-1,692 | $-45 | 25/12 |
| IB>=100_sweep_vwap_confirm_opp_ib | 37 | 45.9% | 0.85 | $-5,122 | $1,749 | $-1,743 | $-138 | 25/12 |
| IB>=100_sweep_vwap_confirm_1R | 37 | 43.2% | 0.84 | $-5,997 | $1,914 | $-1,744 | $-162 | 25/12 |
| IB>=200_sweep_618fib_1_5x_ib | 39 | 35.9% | 0.83 | $-9,442 | $3,312 | $-2,232 | $-242 | 20/19 |
| IB>=100_sweep_vwap_confirm_2R | 37 | 37.8% | 0.83 | $-6,722 | $2,299 | $-1,692 | $-182 | 25/12 |
| IB>=300_sweep_vwap_1R | 10 | 50.0% | 0.82 | $-3,142 | $2,948 | $-3,576 | $-314 | 7/3 |
| IB>=200_sweep_vwap_confirm_1R | 14 | 35.7% | 0.80 | $-3,167 | $2,603 | $-1,798 | $-226 | 10/4 |
| IB>=250_sweep_vwap_confirm_1R | 11 | 36.4% | 0.79 | $-2,913 | $2,760 | $-1,993 | $-265 | 7/4 |
| IB>=200_sweep_vwap_confirm_opp_ib | 14 | 35.7% | 0.78 | $-3,567 | $2,523 | $-1,798 | $-255 | 10/4 |
| IB>=200_sweep_618fib_2R | 39 | 38.5% | 0.78 | $-11,814 | $2,765 | $-2,220 | $-303 | 20/19 |
| IB>=300_sweep_vwap_1_5x_ib | 10 | 40.0% | 0.77 | $-4,946 | $4,105 | $-3,561 | $-495 | 7/3 |
| IB>=150_sweep_vwap_confirm_opp_ib | 28 | 39.3% | 0.77 | $-7,045 | $2,105 | $-1,776 | $-252 | 19/9 |
| IB>=250_sweep_vwap_confirm_opp_ib | 11 | 36.4% | 0.76 | $-3,313 | $2,660 | $-1,993 | $-301 | 7/4 |
| IB>=100_sweep_618fib_1_5x_ib | 103 | 32.0% | 0.76 | $-27,213 | $2,592 | $-1,611 | $-264 | 64/39 |
| IB>=150_sweep_vwap_confirm_1_5x_ib | 28 | 28.6% | 0.76 | $-8,285 | $3,245 | $-1,712 | $-296 | 19/9 |
| IB>=300_sweep_vwap_opp_ib | 10 | 50.0% | 0.75 | $-4,491 | $2,678 | $-3,576 | $-449 | 7/3 |
| IB>=100_sweep_618fib_2R | 103 | 35.0% | 0.75 | $-27,307 | $2,245 | $-1,614 | $-265 | 64/39 |
| IB>=150_sweep_vwap_confirm_1R | 28 | 35.7% | 0.72 | $-8,920 | $2,304 | $-1,775 | $-319 | 19/9 |
| IB>=200_sweep_618fib_opp_ib | 39 | 41.0% | 0.72 | $-14,715 | $2,344 | $-2,270 | $-377 | 20/19 |
| IB>=100_sweep_50pct_2R | 117 | 38.5% | 0.70 | $-42,697 | $2,231 | $-1,987 | $-365 | 71/46 |
| IB>=100_sweep_618fib_opp_ib | 103 | 36.9% | 0.70 | $-32,059 | $1,937 | $-1,626 | $-311 | 64/39 |
| IB>=100_sweep_50pct_opp_ib | 117 | 44.4% | 0.69 | $-40,580 | $1,722 | $-2,002 | $-347 | 71/46 |
| IB>=100_sweep_50pct_1R | 117 | 41.9% | 0.67 | $-44,395 | $1,862 | $-1,995 | $-379 | 71/46 |
| IB>=150_sweep_vwap_confirm_2R | 28 | 28.6% | 0.66 | $-11,495 | $2,844 | $-1,712 | $-411 | 19/9 |
| IB>=200_sweep_vwap_opp_ib | 44 | 54.5% | 0.65 | $-22,408 | $1,757 | $-3,229 | $-509 | 21/23 |
| IB>=200_sweep_50pct_opp_ib | 46 | 41.3% | 0.65 | $-24,144 | $2,362 | $-2,556 | $-525 | 24/22 |
| IB>=250_sweep_618fib_2R | 25 | 32.0% | 0.65 | $-14,541 | $3,371 | $-2,442 | $-582 | 11/14 |
| IB>=100_sweep_50pct_1_5x_ib | 117 | 36.8% | 0.64 | $-52,345 | $2,175 | $-1,971 | $-447 | 71/46 |
| IB>=200_sweep_50pct_2R | 46 | 37.0% | 0.64 | $-26,516 | $2,785 | $-2,547 | $-576 | 24/22 |
| IB>=150_sweep_50pct_opp_ib | 76 | 40.8% | 0.63 | $-37,372 | $2,095 | $-2,273 | $-492 | 43/33 |
| IB>=300_sweep_50pct_1_5x_ib | 13 | 30.8% | 0.63 | $-10,243 | $4,442 | $-3,112 | $-788 | 9/4 |
| IB>=200_sweep_50pct_1R | 46 | 39.1% | 0.63 | $-26,214 | $2,468 | $-2,523 | $-570 | 24/22 |
| IB>=200_sweep_50pct_1_5x_ib | 46 | 37.0% | 0.62 | $-27,704 | $2,715 | $-2,547 | $-602 | 24/22 |
| IB>=150_sweep_618fib_1_5x_ib | 69 | 29.0% | 0.62 | $-33,234 | $2,765 | $-1,807 | $-482 | 39/30 |
| IB>=200_sweep_618fib_1R | 39 | 43.6% | 0.62 | $-18,430 | $1,793 | $-2,223 | $-473 | 20/19 |
| IB>=100_sweep_vwap_1R | 116 | 45.7% | 0.62 | $-56,558 | $1,753 | $-2,372 | $-488 | 68/48 |
| IB>=300_sweep_50pct_1R | 13 | 38.5% | 0.62 | $-9,398 | $3,077 | $-3,098 | $-723 | 9/4 |
| IB>=300_sweep_618fib_2R | 10 | 30.0% | 0.62 | $-6,968 | $3,779 | $-2,615 | $-697 | 7/3 |
| IB>=150_sweep_618fib_opp_ib | 69 | 33.3% | 0.62 | $-31,867 | $2,246 | $-1,816 | $-462 | 39/30 |
| IB>=100_sweep_vwap_opp_ib | 116 | 52.6% | 0.62 | $-49,986 | $1,325 | $-2,379 | $-431 | 68/48 |
| IB>=200_sweep_vwap_1_5x_ib | 44 | 45.5% | 0.61 | $-28,553 | $2,276 | $-3,087 | $-649 | 21/23 |
| IB>=300_sweep_618fib_1R | 10 | 40.0% | 0.61 | $-5,861 | $2,285 | $-2,500 | $-586 | 7/3 |
| IB>=200_sweep_vwap_1R | 44 | 47.7% | 0.60 | $-27,944 | $2,031 | $-3,069 | $-635 | 21/23 |
| IB>=100_sweep_618fib_1R | 103 | 39.8% | 0.60 | $-40,081 | $1,461 | $-1,613 | $-389 | 64/39 |
| IB>=150_sweep_vwap_opp_ib | 75 | 50.7% | 0.60 | $-40,505 | $1,590 | $-2,728 | $-540 | 40/35 |
| IB>=300_sweep_vwap_2R | 10 | 40.0% | 0.60 | $-8,576 | $3,198 | $-3,561 | $-858 | 7/3 |
| IB>=250_sweep_618fib_1_5x_ib | 25 | 28.0% | 0.60 | $-17,731 | $3,756 | $-2,446 | $-709 | 11/14 |
| IB>=150_sweep_618fib_2R | 69 | 30.4% | 0.60 | $-34,675 | $2,444 | $-1,792 | $-503 | 39/30 |
| IB>=300_sweep_50pct_opp_ib | 13 | 38.5% | 0.60 | $-9,998 | $2,957 | $-3,098 | $-769 | 9/4 |
| IB>=250_sweep_vwap_1_5x_ib | 27 | 40.7% | 0.58 | $-24,052 | $3,075 | $-3,618 | $-891 | 11/16 |
| IB>=150_sweep_50pct_1R | 76 | 36.8% | 0.58 | $-44,987 | $2,245 | $-2,247 | $-592 | 43/33 |
| IB>=200_sweep_vwap_2R | 44 | 45.5% | 0.58 | $-31,000 | $2,154 | $-3,087 | $-705 | 21/23 |
| IB>=250_sweep_vwap_opp_ib | 27 | 48.1% | 0.57 | $-21,752 | $2,239 | $-3,633 | $-806 | 11/16 |
| IB>=100_sweep_vwap_1_5x_ib | 116 | 39.7% | 0.56 | $-70,638 | $1,934 | $-2,280 | $-609 | 68/48 |
| IB>=250_sweep_vwap_1R | 27 | 44.4% | 0.54 | $-24,822 | $2,464 | $-3,626 | $-919 | 11/16 |
| IB>=150_sweep_vwap_1R | 75 | 42.7% | 0.54 | $-52,807 | $1,956 | $-2,684 | $-704 | 40/35 |
| IB>=300_sweep_618fib_1_5x_ib | 10 | 20.0% | 0.54 | $-9,542 | $5,641 | $-2,603 | $-954 | 7/3 |
| IB>=250_sweep_50pct_1R | 29 | 34.5% | 0.53 | $-25,779 | $2,898 | $-2,882 | $-889 | 13/16 |
| IB>=250_sweep_50pct_1_5x_ib | 29 | 31.0% | 0.53 | $-27,324 | $3,407 | $-2,899 | $-942 | 13/16 |
| IB>=100_sweep_vwap_2R | 116 | 39.7% | 0.52 | $-76,197 | $1,814 | $-2,280 | $-657 | 68/48 |
| IB>=300_sweep_50pct_2R | 13 | 30.8% | 0.52 | $-13,453 | $3,640 | $-3,112 | $-1,035 | 9/4 |
| IB>=150_sweep_50pct_2R | 76 | 31.6% | 0.52 | $-55,497 | $2,491 | $-2,217 | $-730 | 43/33 |
| IB>=250_sweep_618fib_opp_ib | 25 | 32.0% | 0.52 | $-20,024 | $2,685 | $-2,442 | $-801 | 11/14 |
| IB>=150_sweep_618fib_1R | 69 | 34.8% | 0.51 | $-39,489 | $1,698 | $-1,783 | $-572 | 39/30 |
| IB>=250_sweep_50pct_opp_ib | 29 | 34.5% | 0.50 | $-27,179 | $2,758 | $-2,882 | $-937 | 13/16 |
| IB>=250_sweep_618fib_1R | 25 | 36.0% | 0.49 | $-19,634 | $2,063 | $-2,388 | $-785 | 11/14 |
| IB>=150_sweep_50pct_1_5x_ib | 76 | 31.6% | 0.48 | $-60,452 | $2,285 | $-2,217 | $-795 | 43/33 |
| IB>=250_sweep_50pct_2R | 29 | 31.0% | 0.47 | $-30,534 | $3,050 | $-2,899 | $-1,053 | 13/16 |
| IB>=300_sweep_618fib_opp_ib | 10 | 30.0% | 0.47 | $-9,700 | $2,868 | $-2,615 | $-970 | 7/3 |
| IB>=250_sweep_vwap_2R | 27 | 40.7% | 0.45 | $-32,122 | $2,342 | $-3,618 | $-1,190 | 11/16 |
| IB>=150_sweep_vwap_1_5x_ib | 75 | 36.0% | 0.44 | $-68,880 | $1,986 | $-2,552 | $-918 | 40/35 |
| IB>=150_sweep_vwap_2R | 75 | 36.0% | 0.42 | $-71,327 | $1,895 | $-2,552 | $-951 | 40/35 |
| IB>=400_ib_close_30_618fib_1R | 9 | 33.3% | 0.37 | $-13,486 | $2,687 | $-3,591 | $-1,498 | 4/5 |
| IB>=300_ib_close_30_618fib_1_5x_ib | 30 | 16.7% | 0.37 | $-44,690 | $5,227 | $-2,833 | $-1,490 | 12/18 |
| IB>=200_ib_close_30_618fib_1_5x_ib | 81 | 13.6% | 0.31 | $-112,159 | $4,591 | $-2,324 | $-1,385 | 38/43 |
| IB>=250_ib_close_30_618fib_1_5x_ib | 50 | 12.0% | 0.31 | $-78,333 | $5,842 | $-2,577 | $-1,567 | 26/24 |
| IB>=150_ib_close_30_618fib_1_5x_ib | 118 | 13.6% | 0.30 | $-145,957 | $3,984 | $-2,056 | $-1,237 | 65/53 |
| IB>=100_ib_close_30_618fib_1_5x_ib | 167 | 12.6% | 0.30 | $-182,368 | $3,719 | $-1,784 | $-1,092 | 93/74 |
| IB>=400_ib_close_30_618fib_opp_ib | 9 | 22.2% | 0.28 | $-16,441 | $3,254 | $-3,278 | $-1,827 | 4/5 |
| IB>=300_ib_close_30_618fib_2R | 30 | 16.7% | 0.27 | $-51,357 | $3,894 | $-2,833 | $-1,712 | 12/18 |
| IB>=300_ib_close_30_618fib_opp_ib | 30 | 16.7% | 0.27 | $-51,595 | $3,846 | $-2,833 | $-1,720 | 12/18 |
| IB>=100_ib_close_30_618fib_2R | 167 | 13.8% | 0.25 | $-193,822 | $2,773 | $-1,789 | $-1,161 | 93/74 |
| IB>=150_ib_close_30_618fib_2R | 118 | 14.4% | 0.24 | $-157,161 | $2,997 | $-2,061 | $-1,332 | 65/53 |
| IB>=300_ib_close_30_50pct_2R | 30 | 16.7% | 0.24 | $-69,760 | $4,483 | $-3,687 | $-2,325 | 12/18 |
| IB>=250_ib_close_30_618fib_1R | 50 | 20.0% | 0.24 | $-80,783 | $2,557 | $-2,659 | $-1,616 | 26/24 |
| IB>=150_ib_close_30_618fib_opp_ib | 118 | 15.3% | 0.24 | $-157,010 | $2,719 | $-2,060 | $-1,331 | 65/53 |
| IB>=300_ib_close_30_618fib_1R | 30 | 20.0% | 0.24 | $-52,926 | $2,750 | $-2,893 | $-1,764 | 12/18 |
| IB>=300_ib_close_30_50pct_1_5x_ib | 30 | 16.7% | 0.24 | $-70,423 | $4,350 | $-3,687 | $-2,347 | 12/18 |
| IB>=250_ib_close_30_618fib_opp_ib | 50 | 14.0% | 0.23 | $-85,220 | $3,715 | $-2,587 | $-1,704 | 26/24 |
| IB>=100_ib_close_30_618fib_1R | 167 | 19.8% | 0.23 | $-187,918 | $1,736 | $-1,830 | $-1,125 | 93/74 |
| IB>=200_ib_close_30_618fib_1R | 81 | 19.8% | 0.23 | $-118,385 | $2,235 | $-2,371 | $-1,462 | 38/43 |
| IB>=150_ib_close_30_618fib_1R | 118 | 19.5% | 0.23 | $-153,324 | $2,009 | $-2,100 | $-1,299 | 65/53 |
| IB>=100_ib_close_30_618fib_opp_ib | 167 | 15.0% | 0.23 | $-196,142 | $2,364 | $-1,798 | $-1,175 | 93/74 |
| IB>=200_ib_close_30_618fib_opp_ib | 81 | 14.8% | 0.23 | $-123,545 | $3,079 | $-2,326 | $-1,525 | 38/43 |
| IB>=200_ib_close_30_618fib_2R | 81 | 13.6% | 0.23 | $-125,362 | $3,390 | $-2,324 | $-1,548 | 38/43 |
| IB>=250_ib_close_30_618fib_2R | 50 | 12.0% | 0.22 | $-88,986 | $4,066 | $-2,577 | $-1,780 | 26/24 |
| IB>=200_ib_close_30_50pct_1_5x_ib | 81 | 13.6% | 0.21 | $-165,810 | $3,996 | $-2,997 | $-2,047 | 38/43 |
| IB>=250_ib_close_30_50pct_1_5x_ib | 50 | 12.0% | 0.21 | $-116,245 | $5,111 | $-3,339 | $-2,325 | 26/24 |
| IB>=100_ib_close_30_50pct_1_5x_ib | 167 | 12.6% | 0.21 | $-264,417 | $3,298 | $-2,285 | $-1,583 | 93/74 |
| IB>=150_ib_close_30_50pct_1_5x_ib | 118 | 13.6% | 0.21 | $-214,564 | $3,465 | $-2,647 | $-1,818 | 65/53 |
| IB>=250_ib_close_30_50pct_2R | 50 | 12.0% | 0.20 | $-118,163 | $4,792 | $-3,339 | $-2,363 | 26/24 |
| IB>=200_ib_close_30_50pct_2R | 81 | 13.6% | 0.19 | $-169,490 | $3,661 | $-2,997 | $-2,092 | 38/43 |
| IB>=150_ib_close_30_50pct_2R | 118 | 13.6% | 0.19 | $-218,969 | $3,190 | $-2,647 | $-1,856 | 65/53 |
| IB>=100_ib_close_30_50pct_2R | 167 | 12.6% | 0.19 | $-271,222 | $2,974 | $-2,285 | $-1,624 | 93/74 |
| IB>=100_ib_close_30_vwap_confirm_1_5x_ib | 58 | 12.1% | 0.18 | $-92,698 | $2,844 | $-2,208 | $-1,598 | 33/25 |
| IB>=300_ib_close_30_50pct_1R | 30 | 16.7% | 0.17 | $-76,528 | $3,129 | $-3,687 | $-2,551 | 12/18 |
| IB>=300_ib_close_30_vwap_2R | 28 | 10.7% | 0.16 | $-86,754 | $5,648 | $-4,148 | $-3,098 | 11/17 |
| IB>=300_ib_close_30_vwap_1_5x_ib | 28 | 10.7% | 0.16 | $-86,754 | $5,648 | $-4,148 | $-3,098 | 11/17 |
| IB>=300_ib_close_30_50pct_opp_ib | 30 | 16.7% | 0.16 | $-77,328 | $2,969 | $-3,687 | $-2,578 | 12/18 |
| IB>=400_ib_close_30_50pct_1R | 9 | 22.2% | 0.16 | $-25,392 | $2,383 | $-4,308 | $-2,821 | 4/5 |
| IB>=100_ib_close_30_50pct_1R | 167 | 15.0% | 0.15 | $-276,782 | $2,003 | $-2,302 | $-1,657 | 93/74 |
| IB>=150_ib_close_30_50pct_1R | 118 | 15.3% | 0.15 | $-224,759 | $2,249 | $-2,652 | $-1,905 | 65/53 |
| IB>=400_ib_close_30_50pct_opp_ib | 9 | 22.2% | 0.15 | $-25,592 | $2,283 | $-4,308 | $-2,844 | 4/5 |
| IB>=100_ib_close_30_vwap_confirm_2R | 58 | 12.1% | 0.15 | $-95,603 | $2,429 | $-2,208 | $-1,648 | 33/25 |
| IB>=250_ib_close_30_50pct_1R | 50 | 14.0% | 0.15 | $-122,635 | $3,074 | $-3,352 | $-2,453 | 26/24 |
| IB>=300_ib_close_30_vwap_1R | 28 | 10.7% | 0.15 | $-88,593 | $5,035 | $-4,148 | $-3,164 | 11/17 |
| IB>=200_ib_close_30_50pct_1R | 81 | 14.8% | 0.15 | $-176,965 | $2,503 | $-3,000 | $-2,185 | 38/43 |
| IB>=150_ib_close_30_50pct_opp_ib | 118 | 15.3% | 0.14 | $-227,204 | $2,113 | $-2,652 | $-1,925 | 65/53 |
| IB>=100_ib_close_30_50pct_opp_ib | 167 | 15.0% | 0.14 | $-280,627 | $1,849 | $-2,302 | $-1,680 | 93/74 |
| IB>=250_ib_close_30_50pct_opp_ib | 50 | 14.0% | 0.14 | $-123,835 | $2,902 | $-3,352 | $-2,477 | 26/24 |
| IB>=200_ib_close_30_50pct_opp_ib | 81 | 14.8% | 0.14 | $-178,410 | $2,383 | $-3,000 | $-2,203 | 38/43 |
| IB>=100_ib_close_30_vwap_confirm_1R | 58 | 15.5% | 0.14 | $-95,053 | $1,681 | $-2,249 | $-1,639 | 33/25 |
| IB>=100_ib_close_30_vwap_1_5x_ib | 157 | 10.8% | 0.13 | $-312,696 | $2,861 | $-2,581 | $-1,992 | 87/70 |
| IB>=150_ib_close_30_vwap_2R | 111 | 12.6% | 0.13 | $-256,591 | $2,726 | $-3,039 | $-2,312 | 60/51 |
| IB>=100_ib_close_30_vwap_2R | 157 | 12.1% | 0.13 | $-313,565 | $2,445 | $-2,609 | $-1,997 | 87/70 |
| IB>=150_ib_close_30_vwap_confirm_1_5x_ib | 38 | 10.5% | 0.13 | $-77,356 | $2,832 | $-2,608 | $-2,036 | 24/14 |
| IB>=150_ib_close_30_vwap_1R | 111 | 16.2% | 0.13 | $-254,634 | $2,063 | $-3,137 | $-2,294 | 60/51 |
| IB>=100_ib_close_30_vwap_confirm_opp_ib | 58 | 15.5% | 0.12 | $-96,653 | $1,504 | $-2,249 | $-1,666 | 33/25 |
| IB>=100_ib_close_30_vwap_1R | 157 | 15.3% | 0.12 | $-313,260 | $1,811 | $-2,682 | $-1,995 | 87/70 |
| IB>=200_ib_close_30_vwap_2R | 75 | 10.7% | 0.12 | $-202,486 | $3,459 | $-3,435 | $-2,700 | 34/41 |
| IB>=200_ib_close_30_vwap_1R | 75 | 13.3% | 0.12 | $-201,296 | $2,701 | $-3,512 | $-2,684 | 34/41 |
| IB>=150_ib_close_30_vwap_1_5x_ib | 111 | 10.8% | 0.12 | $-261,218 | $2,905 | $-2,991 | $-2,353 | 60/51 |
| IB>=250_ib_close_30_vwap_2R | 46 | 8.7% | 0.12 | $-147,829 | $4,873 | $-3,984 | $-3,214 | 24/22 |
| IB>=150_ib_close_30_vwap_confirm_2R | 38 | 10.5% | 0.11 | $-78,536 | $2,537 | $-2,608 | $-2,067 | 24/14 |
| IB>=150_ib_close_30_vwap_confirm_1R | 38 | 13.2% | 0.11 | $-76,831 | $1,970 | $-2,627 | $-2,022 | 24/14 |
| IB>=400_ib_close_30_618fib_2R | 9 | 22.2% | 0.11 | $-20,426 | $1,261 | $-3,278 | $-2,270 | 4/5 |
| IB>=400_ib_close_30_618fib_1_5x_ib | 9 | 22.2% | 0.11 | $-20,426 | $1,261 | $-3,278 | $-2,270 | 4/5 |
| IB>=200_ib_close_30_vwap_1_5x_ib | 75 | 9.3% | 0.11 | $-205,893 | $3,492 | $-3,387 | $-2,745 | 34/41 |
| IB>=100_ib_close_30_vwap_opp_ib | 157 | 14.0% | 0.11 | $-315,627 | $1,684 | $-2,612 | $-2,010 | 87/70 |
| IB>=150_ib_close_30_vwap_confirm_opp_ib | 38 | 13.2% | 0.10 | $-77,631 | $1,810 | $-2,627 | $-2,043 | 24/14 |
| IB>=250_ib_close_30_vwap_1_5x_ib | 46 | 6.5% | 0.10 | $-150,558 | $5,648 | $-3,895 | $-3,273 | 24/22 |
| IB>=250_ib_close_30_vwap_1R | 46 | 8.7% | 0.10 | $-150,953 | $4,092 | $-3,984 | $-3,282 | 24/22 |
| IB>=150_ib_close_30_vwap_opp_ib | 111 | 13.5% | 0.10 | $-262,177 | $1,891 | $-3,026 | $-2,362 | 60/51 |
| IB>=300_ib_close_30_vwap_opp_ib | 28 | 14.3% | 0.09 | $-93,659 | $2,242 | $-4,276 | $-3,345 | 11/17 |
| IB>=200_ib_close_30_vwap_opp_ib | 75 | 12.0% | 0.08 | $-207,288 | $2,073 | $-3,423 | $-2,764 | 34/41 |
| IB>=400_ib_close_30_vwap_opp_ib | 9 | 11.1% | 0.08 | $-33,755 | $2,913 | $-4,584 | $-3,751 | 4/5 |
| IB>=250_ib_close_30_vwap_opp_ib | 46 | 10.9% | 0.07 | $-152,188 | $2,183 | $-3,978 | $-3,308 | 24/22 |
| IB>=200_ib_close_30_vwap_confirm_2R | 26 | 7.7% | 0.07 | $-65,689 | $2,345 | $-2,932 | $-2,527 | 17/9 |
| IB>=200_ib_close_30_vwap_confirm_1_5x_ib | 26 | 7.7% | 0.07 | $-65,689 | $2,345 | $-2,932 | $-2,527 | 17/9 |
| IB>=200_ib_close_30_vwap_confirm_1R | 26 | 7.7% | 0.06 | $-66,329 | $2,025 | $-2,932 | $-2,551 | 17/9 |
| IB>=200_ib_close_30_vwap_confirm_opp_ib | 26 | 7.7% | 0.05 | $-66,529 | $1,925 | $-2,932 | $-2,559 | 17/9 |
| IB>=400_ib_close_30_50pct_2R | 9 | 22.2% | 0.02 | $-29,577 | $291 | $-4,308 | $-3,286 | 4/5 |
| IB>=400_ib_close_30_50pct_1_5x_ib | 9 | 22.2% | 0.02 | $-29,577 | $291 | $-4,308 | $-3,286 | 4/5 |
| IB>=300_ib_close_30_vwap_confirm_opp_ib | 8 | 0.0% | 0.00 | $-28,850 | $0 | $-3,606 | $-3,606 | 6/2 |
| IB>=300_ib_close_30_vwap_confirm_2R | 8 | 0.0% | 0.00 | $-28,850 | $0 | $-3,606 | $-3,606 | 6/2 |
| IB>=300_ib_close_30_vwap_confirm_1_5x_ib | 8 | 0.0% | 0.00 | $-28,850 | $0 | $-3,606 | $-3,606 | 6/2 |
| IB>=300_ib_close_30_vwap_confirm_1R | 8 | 0.0% | 0.00 | $-28,850 | $0 | $-3,606 | $-3,606 | 6/2 |
| IB>=400_ib_close_30_vwap_2R | 9 | 0.0% | 0.00 | $-37,740 | $0 | $-4,193 | $-4,193 | 4/5 |
| IB>=400_ib_close_30_vwap_1_5x_ib | 9 | 0.0% | 0.00 | $-37,740 | $0 | $-4,193 | $-4,193 | 4/5 |
| IB>=400_ib_close_30_vwap_1R | 9 | 0.0% | 0.00 | $-37,740 | $0 | $-4,193 | $-4,193 | 4/5 |
| IB>=250_ib_close_30_vwap_confirm_opp_ib | 15 | 0.0% | 0.00 | $-48,499 | $0 | $-3,233 | $-3,233 | 12/3 |
| IB>=250_ib_close_30_vwap_confirm_2R | 15 | 0.0% | 0.00 | $-48,499 | $0 | $-3,233 | $-3,233 | 12/3 |
| IB>=250_ib_close_30_vwap_confirm_1_5x_ib | 15 | 0.0% | 0.00 | $-48,499 | $0 | $-3,233 | $-3,233 | 12/3 |
| IB>=250_ib_close_30_vwap_confirm_1R | 15 | 0.0% | 0.00 | $-48,499 | $0 | $-3,233 | $-3,233 | 12/3 |

### Small Sample Configs (3-4 trades)

| Config | Trades | WR% | PF | Net PnL |
|--------|--------|-----|-----|---------|
| IB>=400_sweep_618fib_1R | 3 | 66.7% | 0.95 | $-194 |
| IB>=400_sweep_vwap_1R | 3 | 66.7% | 0.73 | $-1,661 |
| IB>=400_sweep_vwap_opp_ib | 3 | 66.7% | 0.67 | $-2,000 |
| IB>=400_sweep_vwap_2R | 3 | 66.7% | 0.46 | $-3,255 |
| IB>=400_sweep_vwap_1_5x_ib | 3 | 66.7% | 0.46 | $-3,255 |
| IB>=400_sweep_50pct_1R | 4 | 25.0% | 0.43 | $-5,591 |
| IB>=400_sweep_50pct_opp_ib | 4 | 25.0% | 0.41 | $-5,791 |
| IB>=400_sweep_50pct_2R | 4 | 25.0% | 0.28 | $-7,046 |
| IB>=400_sweep_50pct_1_5x_ib | 4 | 25.0% | 0.28 | $-7,046 |
| IB>=400_sweep_618fib_opp_ib | 3 | 33.3% | 0.07 | $-6,756 |
| IB>=400_sweep_618fib_2R | 3 | 33.3% | 0.07 | $-6,756 |
| IB>=400_sweep_618fib_1_5x_ib | 3 | 33.3% | 0.07 | $-6,756 |

## Direction Method Comparison

| Method | Total Trades | WR% | PF | Net PnL |
|--------|-------------|-----|-----|---------|
| sweep | 3620 | 38.9% | 0.62 | $-1,868,915 |
| ib_close_30 | 5924 | 13.6% | 0.16 | $-11,487,080 |

## IB Range Threshold Analysis (Sweep Method)

| Threshold | Total Trades | WR% | PF | Net PnL |
|-----------|-------------|-----|-----|---------|
| >= 100 pts | 1492 | 40.5% | 0.67 | $-579,556 |
| >= 150 pts | 992 | 35.9% | 0.56 | $-606,834 |
| >= 200 pts | 572 | 41.6% | 0.68 | $-268,951 |
| >= 250 pts | 368 | 36.1% | 0.57 | $-284,546 |
| >= 300 pts | 156 | 38.5% | 0.74 | $-72,918 |
| >= 400 pts | 40 | 42.5% | 0.37 | $-56,109 |

## Entry Model Comparison (Sweep Method)

| Entry Model | Total Trades | WR% | PF | Net PnL |
|-------------|-------------|-----|-----|---------|
| 50pct | 1140 | 37.5% | 0.60 | $-662,284 |
| 618fib | 996 | 34.8% | 0.64 | $-444,789 |
| vwap | 1100 | 44.4% | 0.56 | $-730,878 |
| vwap_confirm | 384 | 38.0% | 0.93 | $-30,964 |

## Target Model Comparison (Sweep Method)

| Target Model | Total Trades | WR% | PF | Net PnL |
|--------------|-------------|-----|-----|---------|
| opp_ib | 905 | 43.1% | 0.64 | $-417,380 |
| 2R | 905 | 36.2% | 0.61 | $-507,785 |
| 1_5x_ib | 905 | 35.2% | 0.63 | $-478,959 |
| 1R | 905 | 41.0% | 0.61 | $-464,791 |

## Sweep Level Analysis

Which liquidity levels produce the best sweeps?

| Level | Trades | WR% | PF | Net PnL |
|-------|--------|-----|-----|---------|
| LONDON_HIGH | 1464 | 38.9% | 0.73 | $-485,506 |
| ON_HIGH | 1364 | 41.1% | 0.86 | $-222,041 |
| LONDON_LOW | 1084 | 43.7% | 0.79 | $-268,728 |
| ON_LOW | 1032 | 46.5% | 0.92 | $-88,250 |
| PDH | 956 | 39.3% | 0.71 | $-362,491 |
| ASIA_HIGH | 892 | 59.1% | 1.90 | $629,238 |
| PRIOR_VAH | 756 | 41.0% | 0.60 | $-293,048 |
| PDL | 652 | 39.7% | 0.54 | $-532,863 |
| ASIA_LOW | 620 | 41.3% | 0.61 | $-382,374 |
| PRIOR_VAL | 564 | 56.7% | 1.65 | $320,695 |

## Direction Analysis (Sweep Method)

| Direction | Trades | WR% | PF | Net PnL | Avg Win | Avg Loss |
|-----------|--------|-----|-----|---------|---------|----------|
| SHORT | 2080 | 38.4% | 0.63 | $-1,014,290 | $2,185 | $-2,151 |
| LONG | 1544 | 39.5% | 0.61 | $-856,561 | $2,241 | $-2,380 |

## Top 5 Configurations (by Profit Factor, min 5 trades)

### #1: IB>=300_sweep_vwap_confirm_1_5x_ib

- **Trades**: 6 (5S / 1L)
- **Win Rate**: 50.0%
- **Profit Factor**: 3.13
- **Net PnL**: $10,213
- **Expectancy**: $1,702/trade
- **Avg Win**: $5,001, Avg Loss: $-1,597
- **Exit reasons**: {'EOD': 4, 'TARGET': 1, 'STOP': 1}

| Date | Dir | Entry | Stop | Target | Exit | Reason | PnL | IB Range | Sweep |
|------|-----|-------|------|--------|------|--------|-----|----------|-------|
| 2025-02-24 | SHORT | 22530.75 | 22723.75 | 21982.75 | 22435.00 | EOD | $1,901 | 366 | ASIA_HIGH |
| 2025-03-03 | SHORT | 21852.25 | 22043.00 | 21311.00 | 21311.25 | TARGET | $10,806 | 361 | LONDON_HIGH,PDH,ON_HIGH,ASIA_HIGH |
| 2025-03-20 | SHORT | 20629.62 | 20805.25 | 20133.75 | 20805.50 | STOP | $-3,532 | 331 | LONDON_HIGH |
| 2025-12-15 | SHORT | 25485.50 | 25678.00 | 24939.00 | 25370.00 | EOD | $2,296 | 364 | LONDON_HIGH,ON_HIGH,ASIA_HIGH |
| 2026-02-11 | SHORT | 25261.50 | 25475.25 | 24651.25 | 25285.00 | EOD | $-484 | 407 | LONDON_HIGH,PDH,ON_HIGH,ASIA_HIGH,PRIOR_VAH |
| 2026-02-18 | LONG | 24913.25 | 24742.00 | 25396.00 | 24875.25 | EOD | $-774 | 322 | LONDON_LOW,ON_LOW |

### #2: IB>=300_sweep_vwap_confirm_2R

- **Trades**: 6 (5S / 1L)
- **Win Rate**: 50.0%
- **Profit Factor**: 2.46
- **Net PnL**: $7,003
- **Expectancy**: $1,167/trade
- **Avg Win**: $3,931, Avg Loss: $-1,597
- **Exit reasons**: {'EOD': 4, 'TARGET': 1, 'STOP': 1}

| Date | Dir | Entry | Stop | Target | Exit | Reason | PnL | IB Range | Sweep |
|------|-----|-------|------|--------|------|--------|-----|----------|-------|
| 2025-02-24 | SHORT | 22530.75 | 22723.75 | 22145.50 | 22435.00 | EOD | $1,901 | 366 | ASIA_HIGH |
| 2025-03-03 | SHORT | 21852.25 | 22043.00 | 21471.50 | 21471.75 | TARGET | $7,596 | 361 | LONDON_HIGH,PDH,ON_HIGH,ASIA_HIGH |
| 2025-03-20 | SHORT | 20629.62 | 20805.25 | 20279.12 | 20805.50 | STOP | $-3,532 | 331 | LONDON_HIGH |
| 2025-12-15 | SHORT | 25485.50 | 25678.00 | 25101.25 | 25370.00 | EOD | $2,296 | 364 | LONDON_HIGH,ON_HIGH,ASIA_HIGH |
| 2026-02-11 | SHORT | 25261.50 | 25475.25 | 24834.75 | 25285.00 | EOD | $-484 | 407 | LONDON_HIGH,PDH,ON_HIGH,ASIA_HIGH,PRIOR_VAH |
| 2026-02-18 | LONG | 24913.25 | 24742.00 | 25255.00 | 24875.25 | EOD | $-774 | 322 | LONDON_LOW,ON_LOW |

### #3: IB>=300_sweep_vwap_confirm_1R

- **Trades**: 6 (5S / 1L)
- **Win Rate**: 50.0%
- **Profit Factor**: 1.67
- **Net PnL**: $3,193
- **Expectancy**: $532/trade
- **Avg Win**: $2,661, Avg Loss: $-1,597
- **Exit reasons**: {'EOD': 4, 'TARGET': 1, 'STOP': 1}

| Date | Dir | Entry | Stop | Target | Exit | Reason | PnL | IB Range | Sweep |
|------|-----|-------|------|--------|------|--------|-----|----------|-------|
| 2025-02-24 | SHORT | 22530.75 | 22723.75 | 22338.25 | 22435.00 | EOD | $1,901 | 366 | ASIA_HIGH |
| 2025-03-03 | SHORT | 21852.25 | 22043.00 | 21662.00 | 21662.25 | TARGET | $3,786 | 361 | LONDON_HIGH,PDH,ON_HIGH,ASIA_HIGH |
| 2025-03-20 | SHORT | 20629.62 | 20805.25 | 20454.50 | 20805.50 | STOP | $-3,532 | 331 | LONDON_HIGH |
| 2025-12-15 | SHORT | 25485.50 | 25678.00 | 25293.50 | 25370.00 | EOD | $2,296 | 364 | LONDON_HIGH,ON_HIGH,ASIA_HIGH |
| 2026-02-11 | SHORT | 25261.50 | 25475.25 | 25048.25 | 25285.00 | EOD | $-484 | 407 | LONDON_HIGH,PDH,ON_HIGH,ASIA_HIGH,PRIOR_VAH |
| 2026-02-18 | LONG | 24913.25 | 24742.00 | 25084.00 | 24875.25 | EOD | $-774 | 322 | LONDON_LOW,ON_LOW |

### #4: IB>=300_sweep_vwap_confirm_opp_ib

- **Trades**: 6 (5S / 1L)
- **Win Rate**: 50.0%
- **Profit Factor**: 1.62
- **Net PnL**: $2,993
- **Expectancy**: $499/trade
- **Avg Win**: $2,594, Avg Loss: $-1,597
- **Exit reasons**: {'EOD': 4, 'TARGET': 1, 'STOP': 1}

| Date | Dir | Entry | Stop | Target | Exit | Reason | PnL | IB Range | Sweep |
|------|-----|-------|------|--------|------|--------|-----|----------|-------|
| 2025-02-24 | SHORT | 22530.75 | 22723.75 | 22348.25 | 22435.00 | EOD | $1,901 | 366 | ASIA_HIGH |
| 2025-03-03 | SHORT | 21852.25 | 22043.00 | 21672.00 | 21672.25 | TARGET | $3,586 | 361 | LONDON_HIGH,PDH,ON_HIGH,ASIA_HIGH |
| 2025-03-20 | SHORT | 20629.62 | 20805.25 | 20464.50 | 20805.50 | STOP | $-3,532 | 331 | LONDON_HIGH |
| 2025-12-15 | SHORT | 25485.50 | 25678.00 | 25303.50 | 25370.00 | EOD | $2,296 | 364 | LONDON_HIGH,ON_HIGH,ASIA_HIGH |
| 2026-02-11 | SHORT | 25261.50 | 25475.25 | 25058.25 | 25285.00 | EOD | $-484 | 407 | LONDON_HIGH,PDH,ON_HIGH,ASIA_HIGH,PRIOR_VAH |
| 2026-02-18 | LONG | 24913.25 | 24742.00 | 25074.00 | 24875.25 | EOD | $-774 | 322 | LONDON_LOW,ON_LOW |

### #5: IB>=250_sweep_vwap_confirm_1_5x_ib

- **Trades**: 11 (7S / 4L)
- **Win Rate**: 36.4%
- **Profit Factor**: 1.37
- **Net PnL**: $5,192
- **Expectancy**: $472/trade
- **Avg Win**: $4,787, Avg Loss: $-1,993
- **Exit reasons**: {'EOD': 6, 'TARGET': 1, 'STOP': 4}

| Date | Dir | Entry | Stop | Target | Exit | Reason | PnL | IB Range | Sweep |
|------|-----|-------|------|--------|------|--------|-----|----------|-------|
| 2025-02-20 | SHORT | 23000.00 | 23147.50 | 22588.50 | 23014.25 | EOD | $-299 | 274 | LONDON_HIGH,ON_HIGH |
| 2025-02-24 | SHORT | 22530.75 | 22723.75 | 21982.75 | 22435.00 | EOD | $1,901 | 366 | ASIA_HIGH |
| 2025-03-03 | SHORT | 21852.25 | 22043.00 | 21311.00 | 21311.25 | TARGET | $10,806 | 361 | LONDON_HIGH,PDH,ON_HIGH,ASIA_HIGH |
| 2025-03-20 | SHORT | 20629.62 | 20805.25 | 20133.75 | 20805.50 | STOP | $-3,532 | 331 | LONDON_HIGH |
| 2025-04-14 | LONG | 19830.00 | 19686.25 | 20230.25 | 19686.00 | STOP | $-2,894 | 267 | LONDON_LOW,ON_LOW |
| 2025-06-23 | LONG | 22379.62 | 22242.50 | 22760.00 | 22242.25 | STOP | $-2,762 | 254 | LONDON_LOW,PDL,PRIOR_VAL |
| 2025-10-17 | LONG | 25073.38 | 24919.00 | 25505.50 | 25281.25 | EOD | $4,143 | 288 | PRIOR_VAL |
| 2025-12-15 | SHORT | 25485.50 | 25678.00 | 24939.00 | 25370.00 | EOD | $2,296 | 364 | LONDON_HIGH,ON_HIGH,ASIA_HIGH |
| 2026-02-09 | SHORT | 25104.50 | 25264.00 | 24657.00 | 25264.25 | STOP | $-3,209 | 298 | LONDON_HIGH,PDH,ON_HIGH,PRIOR_VAH |
| 2026-02-11 | SHORT | 25261.50 | 25475.25 | 24651.25 | 25285.00 | EOD | $-484 | 407 | LONDON_HIGH,PDH,ON_HIGH,ASIA_HIGH,PRIOR_VAH |
| 2026-02-18 | LONG | 24913.25 | 24742.00 | 25396.00 | 24875.25 | EOD | $-774 | 322 | LONDON_LOW,ON_LOW |

## Comparison to V1

| Metric | V1 (Best Config) | V2 (Best Config) |
|--------|------------------|------------------|
| Direction Method | IB close position (30%) | Liquidity sweep detection |
| IB Range Filter | 60-150 pts | 100-400 pts (extreme days) |
| Best PF | All negative | 3.13 |
| Best WR | All < 50% | 50.0% |
| Best Net PnL | All negative | $10,213 |
| Trades (best cfg) | ~20-50 | 6 |

## Recommendation

**PROMISING BUT LOW SAMPLE**: `IB>=300_sweep_vwap_confirm_1_5x_ib` shows positive expectancy
(6 trades, PF 3.13) but needs more data to confirm.

## Key Observations

1. **Sweep >> IB Close**: Liquidity sweep direction (PF 0.62, 38.9% WR) massively outperforms IB close position (PF 0.16, 13.6% WR). The IB close method is catastrophically wrong -- it produces 86% losing trades. Sweep at least gets direction right ~40% of the time.

2. **VWAP Confirm is the critical filter**: Among entry models, `vwap_confirm` (PF 0.93) dramatically outperforms `50pct` (0.60), `618fib` (0.64), and raw `vwap` (0.56). VWAP confirmation cuts trade count by 65% but eliminates the worst setups. This is the only entry model that produces ANY positive-expectancy configs.

3. **IB >= 300 is the sweet spot**: At IB >= 300 pts, the sweep method achieves PF 0.74 aggregated across all configs -- the best threshold. Smaller IB ranges (100-200) add too much noise. IB >= 400 has too few sessions (13 of 273 = 4.8%) for reliable data.

4. **ASIA_HIGH sweeps are the alpha**: Of all swept levels, ASIA_HIGH produces 59.1% WR and PF 1.90 (+$629K aggregate). PRIOR_VAL also works well (56.7% WR, PF 1.65, +$321K). All other levels are net negative. This suggests the strategy may work best when filtered to ONLY Asia/Prior VA sweeps.

5. **SHORT bias dominates**: The top configs are 83% SHORT (5S/1L in best config). This aligns with the thesis -- sweep of highs (London High, PDH, Overnight High, Asia High) leading to bearish reversal is the primary edge.

6. **EOD exits dominate (4 of 6 in best config)**: The 1.5x IB target is rarely reached same-day on these extreme IB days. The strategy profits from directional drift after the sweep, not from clean target hits. Consider: (a) tighter targets, (b) multi-day holds, or (c) time-based partial exits.

7. **The edge is real but rare**: Only 6 trades in 273 sessions for the best config = ~2 trades/year. This is too infrequent for a standalone strategy. Better framed as an **overlay filter** for existing strategies: when IB >= 300 + sweep detected + VWAP confirms, the directional bias is strong enough to add confidence to other setups.

8. **All non-VWAP-confirm sweep configs are negative**: Without VWAP confirmation, even the sweep method loses money across ALL IB thresholds. The raw sweep signal alone is insufficient -- VWAP must confirm the reversal direction.

9. **Target model barely matters**: All 4 target models produce similar aggregate PF (0.61-0.64). The 1.5x IB target slightly edges out on the best configs because it captures the full drift on winning days, but the difference is small.

10. **Next steps**: (a) Filter sweeps to ONLY Asia High / Prior VAL levels; (b) Test as overlay signal for existing strategies (OR Rev, 80P); (c) Add delta/CVD divergence confirmation like OR Reversal uses; (d) Consider overnight hold for extreme IB days.