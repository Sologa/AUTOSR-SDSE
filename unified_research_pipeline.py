#!/usr/bin/env python3
"""
統一的科研論文處理管道
整合數據爬取、類別過濾、期刊信息處理等功能

功能：
1. 從 arXiv 爬取 overview/review/survey 論文
2. 過濾指定類別的論文
3. 獲取期刊/會議信息
4. 生成多種輸出格式
5. 提供詳細統計報告
"""

import requests
import xml.etree.ElementTree as ET
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from urllib.parse import quote
import argparse

@dataclass
class PipelineConfig:
    """管道配置"""
    keywords: List[str] = None
    target_categories: List[str] = None
    max_papers_per_keyword: int = 5000
    delay_between_requests: float = 1.0
    enable_journal_lookup: bool = True
    output_formats: List[str] = None

    def __post_init__(self):
        if self.keywords is None:
            self.keywords = ["overview", "review", "survey"]
        if self.target_categories is None:
            self.target_categories = ["cs.CL", "cs.LG", "cs.DL", "cs.AI", "cs.IR", "cs.SE"]
        if self.output_formats is None:
            self.output_formats = ["json", "jsonl", "summary"]

class ArxivPipeline:
    """統一的 arXiv 處理管道"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })

        # 統計信息
        self.stats = {
            'total_papers_found': 0,
            'papers_after_filtering': 0,
            'papers_with_doi': 0,
            'papers_with_journal_info': 0,
            'start_time': datetime.now(),
            'end_time': None,
            'categories_count': {},
            'keywords_count': {}
        }

    def search_arxiv_papers(self, keyword: str, max_results: int = 5000) -> List[Dict]:
        """搜索 arXiv 論文"""

        print(f"🔍 搜索關鍵詞: {keyword}")

        papers = []
        page = 0
        base_url = "http://export.arxiv.org/api/query"

        while len(papers) < max_results:
            start = page * 100

            params = {
                'search_query': f'ti:"{keyword}"',
                'start': start,
                'max_results': min(100, max_results - len(papers)),
                'sortBy': 'relevance',
                'sortOrder': 'descending'
            }

            try:
                response = self.session.get(base_url, params=params, timeout=30)
                response.raise_for_status()

                root = ET.fromstring(response.content)
                ns = {'atom': 'http://www.w3.org/2005/Atom', 'arxiv': 'http://arxiv.org/schemas/atom'}

                entries = root.findall('atom:entry', ns)

                if not entries:
                    break  # 沒有更多結果

                for entry in entries:
                    paper_data = self.extract_paper_data(entry, ns)
                    if paper_data:
                        papers.append(paper_data)

                page += 1
                time.sleep(self.config.delay_between_requests)

            except Exception as e:
                print(f"   ❌ 搜索失敗: {e}")
                break

        print(f"   ✅ 找到 {len(papers)} 篇論文")
        return papers

    def extract_paper_data(self, entry, ns) -> Optional[Dict]:
        """從 XML 條目提取論文數據"""

        try:
            # 基本信息
            title_elem = entry.find('atom:title', ns)
            title = title_elem.text.strip() if title_elem is not None else ""

            id_elem = entry.find('atom:id', ns)
            arxiv_id = id_elem.text.split('/')[-1] if id_elem is not None else ""

            # 摘要
            summary_elem = entry.find('atom:summary', ns)
            abstract = summary_elem.text.strip() if summary_elem is not None else ""

            # 作者
            authors = []
            for author in entry.findall('atom:author', ns):
                name_elem = author.find('atom:name', ns)
                if name_elem is not None:
                    authors.append(name_elem.text)
            authors_str = '; '.join(authors)

            # 發佈日期和年份
            published_elem = entry.find('atom:published', ns)
            published_date = ""
            year = ""
            if published_elem is not None and published_elem.text:
                published_date = published_elem.text[:10]
                year = published_date[:4]

            # 分類
            categories = []
            for category in entry.findall('atom:category', ns):
                if category.get('term'):
                    categories.append(category.get('term'))
            categories_str = '; '.join(categories)

            # 鏈接
            url_pdf = ""
            url_landing = ""
            doi = ""

            for link in entry.findall('atom:link', ns):
                if link.get('title') == 'pdf':
                    url_pdf = link.get('href', '')
                elif link.get('rel') == 'alternate':
                    url_landing = link.get('href', '')
                elif link.get('title') == 'doi':
                    doi = link.get('href', '')

            # 期刊引用信息
            journal_ref = ""
            if self.config.enable_journal_lookup:
                journal_ref_elem = entry.find('arxiv:journal_ref', ns)
                if journal_ref_elem is not None and journal_ref_elem.text:
                    journal_ref = journal_ref_elem.text.strip()

            return {
                'id': f"arxiv:{arxiv_id}",
                'source': 'arXiv',
                'title': title,
                'abstract': abstract,
                'authors': authors_str,
                'venue': 'arXiv',
                'year': year,
                'published_date': published_date,
                'doi': doi,
                'arxiv_id': arxiv_id,
                'url_pdf': url_pdf,
                'url_landing': url_landing,
                'categories': categories_str,
                'journal_ref': journal_ref,
                'search_keyword': '',  # 稍後填充
                'retrieved_at': datetime.now().isoformat()
            }

        except Exception as e:
            print(f"   ❌ 提取論文數據失敗: {e}")
            return None

    def filter_by_categories(self, papers: List[Dict]) -> List[Dict]:
        """根據類別過濾論文"""

        print(f"🎯 過濾類別: {self.config.target_categories}")

        filtered_papers = []
        target_cats = set(self.config.target_categories)

        for paper in papers:
            paper_cats = set(paper['categories'].split('; ')) if paper['categories'] else set()

            # 檢查是否包含目標類別
            if paper_cats & target_cats:
                filtered_papers.append(paper)

                # 統計類別
                for cat in paper_cats:
                    if cat in target_cats:
                        self.stats['categories_count'][cat] = self.stats['categories_count'].get(cat, 0) + 1

        print(f"   ✅ 過濾後剩餘 {len(filtered_papers)} 篇論文")
        return filtered_papers

    def enhance_with_journal_info(self, papers: List[Dict]) -> List[Dict]:
        """為論文添加期刊信息"""

        if not self.config.enable_journal_lookup:
            return papers

        print("📚 增強期刊信息")

        enhanced_papers = []

        for paper in papers:
            if paper.get('doi'):
                journal_info = self.lookup_journal_quick(paper['doi'])
                if journal_info:
                    paper.update(journal_info)
                    self.stats['papers_with_journal_info'] += 1

            enhanced_papers.append(paper)

        return enhanced_papers

    def lookup_journal_quick(self, doi: str) -> Optional[Dict]:
        """快速查詢期刊信息"""

        if not doi:
            return None

        try:
            # CrossRef API
            url = f"https://api.crossref.org/works/{doi}"
            response = self.session.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                work = data.get('message', {})

                return {
                    'journal': work.get('container-title', [''])[0] if work.get('container-title') else '',
                    'publisher': work.get('publisher', ''),
                    'volume': work.get('volume', ''),
                    'issue': work.get('issue', ''),
                    'pages': work.get('page', '')
                }

        except Exception as e:
            print(f"   ❌ 期刊查詢失敗: {e}")

        return None

    def save_results(self, papers: List[Dict], output_dir: str = "."):
        """保存結果"""

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON 格式
        if 'json' in self.config.output_formats:
            json_file = f"{output_dir}/filtered_papers_{timestamp}.json"
            # 處理統計中的 datetime 對象
            processed_stats = self.stats.copy()
            if 'start_time' in processed_stats:
                processed_stats['start_time'] = processed_stats['start_time'].isoformat()
            if 'end_time' in processed_stats and processed_stats['end_time']:
                processed_stats['end_time'] = processed_stats['end_time'].isoformat()

            data = {
                'metadata': {
                    'description': '過濾後的論文數據集',
                    'total_papers': len(papers),
                    'target_categories': self.config.target_categories,
                    'search_keywords': self.config.keywords,
                    'generated_at': datetime.now().isoformat(),
                    'stats': processed_stats
                },
                'papers': papers
            }

            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print(f"💾 保存 JSON: {json_file}")

        # JSONL 格式
        if 'jsonl' in self.config.output_formats:
            jsonl_file = f"{output_dir}/filtered_papers_{timestamp}.jsonl"
            with open(jsonl_file, 'w', encoding='utf-8') as f:
                # 寫入 metadata（處理 datetime 對象）
                processed_stats = self.stats.copy()
                if 'start_time' in processed_stats:
                    processed_stats['start_time'] = processed_stats['start_time'].isoformat()
                if 'end_time' in processed_stats and processed_stats['end_time']:
                    processed_stats['end_time'] = processed_stats['end_time'].isoformat()

                metadata = {
                    'type': 'metadata',
                    'description': '過濾後的論文數據集',
                    'total_papers': len(papers),
                    'target_categories': self.config.target_categories,
                    'search_keywords': self.config.keywords,
                    'generated_at': datetime.now().isoformat(),
                    'stats': processed_stats
                }
                f.write(json.dumps(metadata, ensure_ascii=False) + '\n')

                # 寫入論文數據
                for paper in papers:
                    f.write(json.dumps(paper, ensure_ascii=False) + '\n')
            print(f"💾 保存 JSONL: {jsonl_file}")

        # 摘要報告
        if 'summary' in self.config.output_formats:
            summary_file = f"{output_dir}/filtered_papers_{timestamp}_summary.txt"
            self.generate_summary_report(papers, summary_file)
            print(f"💾 保存摘要: {summary_file}")

    def generate_summary_report(self, papers: List[Dict], filename: str):
        """生成摘要報告"""

        with open(filename, 'w', encoding='utf-8') as f:
            f.write("科研論文數據集摘要報告\n")
            f.write("=" * 50 + "\n\n")

            # 基本統計
            f.write("📊 基本統計\n")
            f.write("-" * 30 + "\n")
            f.write(f"總論文數: {len(papers)}\n")
            f.write(f"目標類別: {', '.join(self.config.target_categories)}\n")
            f.write(f"搜索關鍵詞: {', '.join(self.config.keywords)}\n")
            f.write(f"處理時間: {self.stats['start_time'].strftime('%Y-%m-%d %H:%M:%S')} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            # 類別分佈
            f.write("📈 類別分佈\n")
            f.write("-" * 30 + "\n")
            for cat, count in sorted(self.stats['categories_count'].items()):
                f.write(f"{cat}: {count} 篇\n")
            f.write("\n")

            # 關鍵詞統計
            f.write("🔍 關鍵詞統計\n")
            f.write("-" * 30 + "\n")
            for keyword, count in sorted(self.stats['keywords_count'].items()):
                f.write(f"{keyword}: {count} 篇\n")
            f.write("\n")

            # 期刊信息統計
            if self.config.enable_journal_lookup:
                f.write("📚 期刊信息統計\n")
                f.write("-" * 30 + "\n")
                f.write(f"有 DOI 的論文: {self.stats['papers_with_doi']}\n")
                f.write(f"有期刊信息的論文: {self.stats['papers_with_journal_info']}\n")
                f.write("\n")

            # 樣本論文
            f.write("📝 樣本論文\n")
            f.write("-" * 30 + "\n")
            for i, paper in enumerate(papers[:5], 1):
                f.write(f"{i}. {paper['title'][:80]}...\n")
                f.write(f"   作者: {paper['authors'][:50]}...\n")
                f.write(f"   類別: {paper['categories']}\n")
                if paper.get('journal'):
                    f.write(f"   期刊: {paper['journal']}\n")
                f.write("\n")

    def save_journal_papers(self, journal_papers: List[Dict], output_dir: str = "."):
        """保存有期刊信息的論文"""

        print("📚 保存有期刊信息的論文")
        print("=" * 60)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # JSON 格式
        json_file = f"{output_dir}/journal_papers_{timestamp}.json"
        data = {
            'metadata': {
                'description': '有期刊信息的論文數據集',
                'total_papers': len(journal_papers),
                'target_categories': self.config.target_categories,
                'search_keywords': self.config.keywords,
                'generated_at': datetime.now().isoformat(),
                'stats': {
                    'total_journal_papers': len(journal_papers),
                    'journal_categories': {},
                    'journal_years': {}
                }
            },
            'papers': journal_papers
        }

        # 統計期刊論文的類別
        for paper in journal_papers:
            categories = paper.get('categories', '').split('; ')
            for cat in categories:
                if cat in self.config.target_categories:
                    data['metadata']['stats']['journal_categories'][cat] = \
                        data['metadata']['stats']['journal_categories'].get(cat, 0) + 1

        # 統計期刊論文的年份
        for paper in journal_papers:
            year = paper.get('year', '')
            if year:
                data['metadata']['stats']['journal_years'][year] = \
                    data['metadata']['stats']['journal_years'].get(year, 0) + 1

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"💾 保存期刊論文 JSON: {json_file}")

        # JSONL 格式
        jsonl_file = f"{output_dir}/journal_papers_{timestamp}.jsonl"
        with open(jsonl_file, 'w', encoding='utf-8') as f:
            # 寫入 metadata
            metadata = {
                'type': 'metadata',
                'description': '有期刊信息的論文數據集',
                'total_papers': len(journal_papers),
                'target_categories': self.config.target_categories,
                'search_keywords': self.config.keywords,
                'generated_at': datetime.now().isoformat(),
                'stats': data['metadata']['stats']
            }
            f.write(json.dumps(metadata, ensure_ascii=False) + '\n')

            # 寫入論文數據
            for paper in journal_papers:
                f.write(json.dumps(paper, ensure_ascii=False) + '\n')
        print(f"💾 保存期刊論文 JSONL: {jsonl_file}")

        # 生成期刊論文專用摘要
        summary_file = f"{output_dir}/journal_papers_{timestamp}_summary.txt"
        self.generate_journal_summary_report(journal_papers, summary_file)
        print(f"💾 保存期刊論文摘要: {summary_file}")

    def generate_journal_summary_report(self, journal_papers: List[Dict], filename: str):
        """生成期刊論文專用摘要報告"""

        with open(filename, 'w', encoding='utf-8') as f:
            f.write("期刊論文數據集摘要報告\n")
            f.write("=" * 50 + "\n\n")

            # 基本統計
            f.write("📊 期刊論文統計\n")
            f.write("-" * 30 + "\n")
            f.write(f"期刊論文總數: {len(journal_papers)}\n")
            f.write(f"佔總數據集比例: {len(journal_papers)}/{self.stats['papers_after_filtering']} ({len(journal_papers)/self.stats['papers_after_filtering']*100:.1f}%)\n")
            f.write(f"目標類別: {', '.join(self.config.target_categories)}\n\n")

            # 期刊論文類別統計
            journal_categories = {}
            for paper in journal_papers:
                categories = paper.get('categories', '').split('; ')
                for cat in categories:
                    if cat in self.config.target_categories:
                        journal_categories[cat] = journal_categories.get(cat, 0) + 1

            f.write("📚 期刊論文類別分佈\n")
            f.write("-" * 30 + "\n")
            for cat, count in sorted(journal_categories.items()):
                percentage = count / len(journal_papers) * 100
                f.write(f"{cat}: {count} 篇 ({percentage:.1f}%)\n")
            f.write("\n")

            # 期刊論文年份統計
            journal_years = {}
            for paper in journal_papers:
                year = paper.get('year', '')
                if year:
                    journal_years[year] = journal_years.get(year, 0) + 1

            f.write("📅 期刊論文年份分佈\n")
            f.write("-" * 30 + "\n")
            for year, count in sorted(journal_years.items(), reverse=True):
                f.write(f"{year}: {count} 篇\n")
            f.write("\n")

            # 期刊名稱統計
            journal_names = {}
            for paper in journal_papers:
                journal = paper.get('journal_ref', '')
                if journal:
                    # 簡化期刊名稱（取前50個字符）
                    short_name = journal[:50] + "..." if len(journal) > 50 else journal
                    journal_names[short_name] = journal_names.get(short_name, 0) + 1

            f.write("🏷️ 期刊來源統計\n")
            f.write("-" * 30 + "\n")
            for journal, count in sorted(journal_names.items(), key=lambda x: x[1], reverse=True):
                f.write(f"{journal}: {count} 篇\n")
            f.write("\n")

            # 樣本期刊論文
            f.write("📝 樣本期刊論文\n")
            f.write("-" * 30 + "\n")
            for i, paper in enumerate(journal_papers[:5], 1):
                f.write(f"{i}. {paper['title'][:70]}...\n")
                f.write(f"   作者: {paper['authors'][:50]}...\n")
                f.write(f"   期刊: {paper['journal_ref'][:60]}...\n")
                f.write(f"   年份: {paper.get('year', 'N/A')}\n")
                f.write(f"   類別: {paper['categories']}\n")
                f.write("\n")

    def run_pipeline(self) -> List[Dict]:
        """運行完整管道"""

        print("🚀 啟動統一科研論文處理管道")
        print("=" * 60)

        all_papers = []

        # 1. 搜索論文
        for keyword in self.config.keywords:
            papers = self.search_arxiv_papers(keyword, self.config.max_papers_per_keyword)

            # 為論文添加關鍵詞標記
            for paper in papers:
                paper['search_keyword'] = keyword
                self.stats['keywords_count'][keyword] = self.stats['keywords_count'].get(keyword, 0) + 1

            all_papers.extend(papers)
            self.stats['total_papers_found'] += len(papers)

        # 2. 類別過濾
        filtered_papers = self.filter_by_categories(all_papers)
        self.stats['papers_after_filtering'] = len(filtered_papers)

        # 3. 統計 DOI
        for paper in filtered_papers:
            if paper.get('doi'):
                self.stats['papers_with_doi'] += 1

        # 4. 增強期刊信息
        if self.config.enable_journal_lookup:
            filtered_papers = self.enhance_with_journal_info(filtered_papers)

        # 5. 保存結果
        self.save_results(filtered_papers)

        # 6. 額外輸出有期刊信息的論文
        if self.config.enable_journal_lookup:
            journal_papers = [paper for paper in filtered_papers if paper.get('journal_ref')]
            if journal_papers:
                self.save_journal_papers(journal_papers)

        self.stats['end_time'] = datetime.now()

        # 計算期刊論文數量
        journal_papers_count = len([paper for paper in filtered_papers if paper.get('journal_ref')])

        # 最終統計
        print("\n🎯 處理完成統計")
        print("=" * 60)
        print(f"原始論文數: {self.stats['total_papers_found']}")
        print(f"過濾後論文數: {self.stats['papers_after_filtering']}")
        print(f"有 DOI 的論文: {self.stats['papers_with_doi']}")
        print(f"有期刊信息的論文: {self.stats['papers_with_journal_info']}")
        if journal_papers_count > 0:
            print(f"📚 期刊論文數據集: {journal_papers_count} 篇論文已單獨保存")

        return filtered_papers

def main():
    """主函數"""

    parser = argparse.ArgumentParser(description='統一科研論文處理管道')
    parser.add_argument('--keywords', nargs='+',
                       default=['systematic review', 'systematic literature review', 'SLR',
                               'scoping review', 'PRISMA-ScR', 'systematic mapping',
                               'mapping study', 'SMS', 'tertiary study', 'bibliometric analysis',
                               'science mapping', 'co-citation', 'VOSviewer', 'CiteSpace',
                               'meta-analysis', 'umbrella review', 'review of reviews',
                               'taxonomy', 'classification', 'typology', 'framework',
                               'tutorial', 'primer', 'hands-on', 'how-to', 'state of the art',
                               'landscape', 'overview', 'survey', 'comparative study',
                               'benchmark', 'evaluation'],
                       help='搜索關鍵詞')
    parser.add_argument('--categories', nargs='+',
                       default=['cs.CL', 'cs.LG', 'cs.DL', 'cs.AI', 'cs.IR', 'cs.SE'],
                       help='目標類別')
    parser.add_argument('--max-papers', type=int, default=2000,
                       help='每個關鍵詞最大論文數')
    parser.add_argument('--no-journal-lookup', action='store_true',
                       help='禁用期刊信息查詢')
    parser.add_argument('--output-formats', nargs='+', default=['json', 'jsonl', 'summary'],
                       choices=['json', 'jsonl', 'summary'],
                       help='輸出格式')

    args = parser.parse_args()

    # 創建配置
    config = PipelineConfig(
        keywords=args.keywords,
        target_categories=args.categories,
        max_papers_per_keyword=args.max_papers,
        enable_journal_lookup=not args.no_journal_lookup,
        output_formats=args.output_formats
    )

    # 運行管道
    pipeline = ArxivPipeline(config)
    results = pipeline.run_pipeline()

    print(f"\n✅ 處理完成！共獲取 {len(results)} 篇論文")

if __name__ == "__main__":
    main()
