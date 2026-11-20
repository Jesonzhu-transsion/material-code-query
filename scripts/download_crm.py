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
    """Navigate to Task List and wait for task to finish, then download.
    
    Key fix: the Task List page does NOT auto-refresh. We must reload + Search
    on every poll cycle to get fresh task status. Otherwise we keep seeing stale
    data from the initial page load.
    """
    print(f"  Navigating to Task List...")
    await page.goto(CRM_URL, wait_until="networkidle", timeout=60000)
    await wait(page, 3)
    await click_menu(page, ["Report", "Asynchronous Report Mgt", "Task List"])
    await wait(page, 5)
    print(f"  Task List URL: {page.url}")
    
    print(f"  Waiting for task to complete (max {timeout_min} min, polling every 15s)...")
    start = time.time()
    
    while time.time() - start < timeout_min * 60:
        # RELOAD every cycle — the page does not auto-refresh
        await page.reload()
        await wait(page, 5)
        
        # Uncheck "Hide Ended Task" (reverts on reload)
        await page.evaluate("""
            () => {
                const checkboxes = document.querySelectorAll('input[type="checkbox"]');
                for (const cb of checkboxes) {
                    const label = cb.closest('label') || cb.parentElement;
                    const text = (label?.textContent || '').trim();
                    if (text.includes('Hide Ended') || text.includes('hide ended')) {
                        if (cb.checked) cb.click();
                    }
                }
            }
        """)
        await wait(page, 1)
        
        # Click Search to refresh the task list
        await click_btn(page, "Search")
        await wait(page, 5)
        
        elapsed = int(time.time() - start)
        
        # Check task status — scan all rows, matching task name to our report
        result = await page.evaluate("""
            (reportName) => {
                const rows = document.querySelectorAll('.el-table__row');
                let latest = 'no_tasks';
                
                // Normalize report name for matching (e.g. "Inventory_Overview" -> "inventory")
                const reportKey = reportName.toLowerCase().replace(/[^a-z0-9]/g, '');
                
                for (const row of rows) {
                    const cells = row.querySelectorAll('td, .el-table__cell');
                    if (cells.length < 6) continue;
                    
                    const status = (cells[4]?.textContent || '').trim();
                    const taskName = (cells[5]?.textContent || '').trim();
                    const taskKey = taskName.toLowerCase().replace(/[^a-z0-9]/g, '');
                    
                    // Must match our report name
                    if (!taskKey.includes(reportKey)) continue;
                    
                    // Finished / completed — click download
                    if (status.includes('Finished') || status.includes('30-') || 
                        status.includes('Completed') || status.includes('Ended') ||
                        status.includes('Success')) {
                        const operateCell = cells[1];
                        if (operateCell) {
                            // Look for download icon or link
                            const allEls = operateCell.querySelectorAll('*');
                            for (const el of allEls) {
                                const cls = (el.className?.toString() || '').toLowerCase();
                                const text = (el.textContent || '').trim().toLowerCase();
                                if (cls.includes('download') || cls.includes('el-icon-download') ||
                                    text.includes('download') || text === '下载') {
                                    el.click();
                                    return 'clicked_download:' + taskName;
                                }
                            }
                            // Fallback: click first visible element
                            for (const el of allEls) {
                                if (el.offsetParent !== null && el.tagName !== 'DIV') {
                                    el.click();
                                    return 'clicked_operate:' + taskName;
                                }
                            }
                        }
                        latest = 'finished_no_link:' + status + ':' + taskName;
                        continue;
                    }
                    
                    // Running / processing
                    if (status.includes('Running') || status.includes('20-') || 
                        status.includes('Processing') || status.includes('Executing')) {
                        latest = 'running:' + taskName;
                        continue;
                    }
                    
                    // Waiting / queued
                    if (status.includes('Waiting') || status.includes('Pending') || 
                        status.includes('10-') || status.includes('Queue')) {
                        if (latest === 'no_tasks') latest = 'waiting:' + taskName;
                        continue;
                    }
                }
                
                return latest;
            }
        """, report_name)
        
        print(f"  [{elapsed}s] {result}")
        
        if result.startswith('clicked'):
            # Wait for download to trigger and complete
            await wait(page, 20)
            files = [f for f in os.listdir(DOWNLOAD_DIR) 
                     if os.path.getsize(os.path.join(DOWNLOAD_DIR, f)) > 1000]
            if files:
                path = os.path.join(DOWNLOAD_DIR, 
                    max(files, key=lambda f: os.path.getmtime(os.path.join(DOWNLOAD_DIR, f))))
                print(f"  Downloaded: {path} ({os.path.getsize(path)} bytes)")
                return path
            # If no file yet, wait a bit more
            await wait(page, 10)
            files = [f for f in os.listdir(DOWNLOAD_DIR) 
                     if os.path.getsize(os.path.join(DOWNLOAD_DIR, f)) > 1000]
            if files:
                path = os.path.join(DOWNLOAD_DIR, 
                    max(files, key=lambda f: os.path.getmtime(os.path.join(DOWNLOAD_DIR, f))))
                print(f"  Downloaded: {path} ({os.path.getsize(path)} bytes)")
                return path
            print(f"  Download click sent but no file found. Continuing...")
            continue
        
        # If no tasks at all, the export may not have been created yet
        # Keep polling; the task usually appears within 30-60 seconds
    
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
        
        # Capture downloads with rename logic
        # CRM server names both files with "In_Transit_" prefix,
        # so we rename the first download to InventoryOverview
        downloads = []
        download_count = [0]  # mutable counter
        
        async def on_download(d):
            download_count[0] += 1
            raw_path = os.path.join(DOWNLOAD_DIR, d.suggested_filename)
            await d.save_as(raw_path)
            
            # Rename: first download = Inventory Overview, second = In Transit
            if download_count[0] == 1:
                new_name = "InventoryOverview_" + d.suggested_filename
            else:
                new_name = "In_Transit_" + d.suggested_filename
            
            new_path = os.path.join(DOWNLOAD_DIR, new_name)
            os.rename(raw_path, new_path)
            downloads.append(new_path)
            print(f"  [download event] {new_path}")
        
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