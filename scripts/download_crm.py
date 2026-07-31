#!/usr/bin/env python3
"""
CRM Inventory Overview & In Transit Report Downloader for Nigeria.
Based on Pakistan training document approach.
Key differences from Pakistan CRM:
- Nigeria CRM uses async export + Task List menu (not cloud icon panel)
- Need to navigate to Report Center → Asynchronous Report Mgt → Task List
- Uncheck "Hide Ended Task" to see all tasks
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from playwright.async_api import async_playwright

CRM_URL = "https://crm.carlcare.com"
COOKIES_FILE = os.path.join(os.path.dirname(__file__), "crm_cookies.json")
OUTPUT_DIR = "/tmp/crm_exports"
DOWNLOAD_DIR = "/tmp/crm_downloads"

async def click_menu(page, texts):
    """Click menu items sequentially"""
    for text in texts:
        await page.evaluate("""
            (text) => {
                const items = document.querySelectorAll('.el-submenu__title, .el-menu-item');
                for (const item of items) {
                    if (item.textContent.trim() === text) {
                        item.click();
                        return true;
                    }
                }
                return false;
            }
        """, text)
        await page.wait_for_timeout(2000)

async def click_btn(page, text):
    """Click button by exact text"""
    return await page.evaluate("""
        (text) => {
            for (const btn of document.querySelectorAll('button')) {
                if (btn.textContent.trim() === text && btn.offsetParent !== null) {
                    btn.click(); return true;
                }
            }
            return false;
        }
    """, text)

async def wait(page, sec):
    await page.wait_for_timeout(sec * 1000)

async def trigger_export(page, report_name, menu_path):
    """Navigate to report page and trigger export"""
    print(f"\n[{datetime.now()}] === {report_name} ===")
    
    # Navigate to CRM and expand menu
    await page.goto(CRM_URL, wait_until="networkidle", timeout=60000)
    await wait(page, 3)
    await click_menu(page, menu_path)
    await wait(page, 5)
    print(f"  URL: {page.url}")
    
    # Click Search
    print(f"  Clicking Search...")
    await click_btn(page, "Search")
    await wait(page, 10)
    
    count = await page.evaluate("""
        () => { const el = document.querySelector('.el-pagination__total'); return el ? el.textContent : '?'; }
    """)
    print(f"  Records: {count}")
    
    # Click Export
    print(f"  Clicking Export...")
    await click_btn(page, "Export")
    await wait(page, 3)
    
    # Dismiss async dialog
    await click_btn(page, "OK")
    await wait(page, 2)
    print(f"  Export task created!")

async def download_from_task_list(page, report_name, timeout_min=15):
    """Navigate to Task List and wait for task to finish, then download"""
    print(f"  Navigating to Task List...")
    await page.goto(CRM_URL, wait_until="networkidle", timeout=60000)
    await wait(page, 3)
    await click_menu(page, ["Report Center", "Asynchronous Report Mgt", "Task List"])
    await wait(page, 5)
    print(f"  Task List URL: {page.url}")
    
    # Uncheck "Hide Ended Task" to see all tasks
    await page.evaluate("""
        () => {
            const checkboxes = document.querySelectorAll('input[type="checkbox"]');
            for (const cb of checkboxes) {
                const label = cb.closest('label') || cb.parentElement;
                const text = (label?.textContent || '').trim();
                if (text.includes('Hide Ended') || text.includes('hide ended')) {
                    if (cb.checked) cb.click();
                    return 'unchecked';
                }
            }
            return 'not found';
        }
    """)
    await wait(page, 2)
    
    # Change scope to see all tasks
    await page.evaluate("""
        () => {
            // Try to find scope dropdown and select "All"
            const selects = document.querySelectorAll('.el-select, select');
            for (const sel of selects) {
                const label = sel.closest('.el-form-item');
                if (label?.textContent?.includes('Scope')) {
                    sel.click();
                    return 'clicked';
                }
            }
            return 'no scope';
        }
    """)
    await wait(page, 2)
    
    # Click Search on Task List
    await click_btn(page, "Search")
    await wait(page, 5)
    
    print(f"  Waiting for task to complete (max {timeout_min} min)...")
    start = time.time()
    
    while time.time() - start < timeout_min * 60:
        await wait(page, 15)
        elapsed = int(time.time() - start)
        
        # Check task status
        status = await page.evaluate("""
            () => {
                const rows = document.querySelectorAll('.el-table__row');
                for (const row of rows) {
                    const cells = row.querySelectorAll('td, .el-table__cell');
                    const status = cells[4]?.textContent?.trim() || '';
                    const taskName = cells[5]?.textContent?.trim() || '';
                    
                    // Check for finished status
                    if (status.includes('Finished') || status.includes('30-') || status.includes('Completed')) {
                        // Look for download link in operate column (column 1)
                        const operateCell = cells[1];
                        if (operateCell) {
                            const links = operateCell.querySelectorAll('a, button, i, span');
                            for (const link of links) {
                                const cls = (link.className?.toString() || '').toLowerCase();
                                if (cls.includes('download') || cls.includes('el-icon-download')) {
                                    link.click();
                                    return 'clicked_download:' + taskName;
                                }
                            }
                            // Try clicking the first visible element
                            for (const link of links) {
                                if (link.offsetParent !== null) {
                                    link.click();
                                    return 'clicked_operate:' + taskName;
                                }
                            }
                        }
                        return 'finished_no_link:' + status + ':' + taskName;
                    }
                    
                    if (status.includes('Running') || status.includes('20-')) {
                        return 'running:' + taskName;
                    }
                }
                return 'no_tasks';
            }
        """)
        
        print(f"  [{elapsed}s] {status}")
        
        if status.startswith('clicked'):
            await wait(page, 15)
            # Check downloads
            files = [f for f in os.listdir(DOWNLOAD_DIR) if os.path.getsize(os.path.join(DOWNLOAD_DIR, f)) > 1000]
            if files:
                path = os.path.join(DOWNLOAD_DIR, max(files, key=lambda f: os.path.getmtime(os.path.join(DOWNLOAD_DIR, f))))
                print(f"  Downloaded: {path} ({os.path.getsize(path)} bytes)")
                return path
            break
        
        if status == 'no_tasks':
            await page.reload()
            await wait(page, 5)
            await click_btn(page, "Search")
            await wait(page, 5)
    
    return None

async def main():
    print(f"[{datetime.now()}] CRM Nigeria Data Download")
    print(f"  Based on Pakistan training document approach")
    
    with open(COOKIES_FILE) as f:
        cookies = json.load(f)
    
    cookie_list = [{"name": k, "value": v, "domain": ".carlcare.com", "path": "/"} for k, v in cookies.items()]
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    for f in os.listdir(DOWNLOAD_DIR):
        os.remove(os.path.join(DOWNLOAD_DIR, f))
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(accept_downloads=True)
        await ctx.add_cookies(cookie_list)
        page = await ctx.new_page()
        
        # Capture downloads
        downloads = []
        async def on_download(d):
            path = os.path.join(DOWNLOAD_DIR, d.suggested_filename)
            await d.save_as(path)
            downloads.append(path)
            print(f"  [download event] {path}")
        page.on("download", lambda d: asyncio.ensure_future(on_download(d)))
        
        # === Inventory Overview ===
        await trigger_export(page, "Inventory Overview",
            ["WMS", "Queries For Inventory", "Inventory Overview"])
        inv = await download_from_task_list(page, "Inventory_Overview")
        
        # === In Transit Report ===
        await trigger_export(page, "In Transit Report",
            ["WMS", "Logistics Mgt", "In Transit Report"])
        transit = await download_from_task_list(page, "In_Transit")
        
        print(f"\n[{datetime.now()}] === Results ===")
        print(f"  Inventory: {inv or 'FAILED'}")
        print(f"  In Transit: {transit or 'FAILED'}")
        print(f"  Events: {downloads}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())