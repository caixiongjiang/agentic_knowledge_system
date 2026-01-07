// =====================================================
// 清理所有软删除的记录（deleted = 1）
// =====================================================
// 
// 功能说明：
//   此脚本用于物理删除所有标记为已删除（deleted = 1）的记录
//   执行前请确保已备份重要数据！
// 
// 使用方法：
//   方法1: 使用 Python 脚本执行（推荐）
//     uv run python scripts/mongodb/cleanup_deleted_records.py
// 
//   方法2: 使用 mongosh 客户端直接执行
//     mongosh "mongodb://username:password@host:port/database?authSource=admin" \
//       --file scripts/mongodb/cleanup_deleted_records.js
// 
//   方法3: 在 MongoDB Compass/Studio 3T 等工具中手动执行
//     打开此文件，在工具的查询窗口中执行
// 
// 注意事项：
//   - 此操作不可逆，请谨慎执行
//   - 建议先使用预览部分查看要删除的数据
//   - 生产环境建议先备份数据库
// 
// =====================================================

// 使用目标数据库
db = db.getSiblingDB('default');

print('');
print('='.repeat(70));
print('MongoDB 软删除记录清理工具');
print('='.repeat(70));

// =====================================================
// 1. 预览即将删除的记录数
// =====================================================

print('\n📊 步骤1: 预览即将删除的记录...\n');

const collections = [
    'chunk_data',      // Chunk 数据
    'section_data',    // Section 数据
    'document_data'    // Document 数据
];

let totalCount = 0;
const stats = {};

print('即将删除的记录统计：');
print('-'.repeat(50));

collections.forEach(collectionName => {
    const count = db.getCollection(collectionName).countDocuments({ deleted: 1 });
    stats[collectionName] = count;
    totalCount += count;
    
    if (count > 0) {
        print(`  ${collectionName.padEnd(30)} ${count.toString().padStart(5)} 条`);
    }
});

print('-'.repeat(50));
print(`  总计：${totalCount.toString().padStart(36)} 条`);

if (totalCount === 0) {
    print('\n✓ 数据库中没有需要清理的记录（deleted=1）');
    quit();
}

// =====================================================
// 2. 确认提示
// =====================================================

print('\n⚠️  警告：此操作将物理删除上述记录，不可恢复！');
print('   如需执行清理，请取消注释下方的清理代码段');
print('   建议在生产环境执行前先备份数据库\n');

// =====================================================
// 3. 物理删除所有软删除的记录
// =====================================================
// 
// 取消下方注释以执行清理操作
// 
// print('='.repeat(70));
// print('开始清理软删除记录');
// print('='.repeat(70));
// print('');
// 
// let totalDeleted = 0;
// const deletedStats = {};
// 
// collections.forEach(collectionName => {
//     const collection = db.getCollection(collectionName);
//     const count = collection.countDocuments({ deleted: 1 });
//     
//     if (count > 0) {
//         // 执行删除
//         const result = collection.deleteMany({ deleted: 1 });
//         const deletedCount = result.deletedCount;
//         
//         deletedStats[collectionName] = deletedCount;
//         totalDeleted += deletedCount;
//         
//         print(`✓ ${collectionName}: 删除 ${deletedCount} 条记录`);
//     } else {
//         print(`  ${collectionName}: 无需清理`);
//     }
// });
// 
// print('');
// print('='.repeat(70));
// print(`清理完成，共删除 ${totalDeleted} 条记录`);
// print('='.repeat(70));
// 
// =====================================================
// 4. 验证清理结果
// =====================================================
// 
// 取消下方注释以验证清理结果
// 
// print('\n📊 验证清理结果：\n');
// 
// collections.forEach(collectionName => {
//     const remaining = db.getCollection(collectionName).countDocuments({ deleted: 1 });
//     print(`  ${collectionName.padEnd(30)} 剩余 ${remaining} 条`);
// });
// 
// print('');

// =====================================================
// 快速执行版本（直接删除，无需手动取消注释）
// =====================================================
// 
// 如需直接执行清理，请运行以下命令：
// 
//   mongosh "mongodb://username:password@host:port/database?authSource=admin" \
//     --eval "const AUTO_CONFIRM = true;" \
//     --file scripts/mongodb/cleanup_deleted_records.js
// 

if (typeof AUTO_CONFIRM !== 'undefined' && AUTO_CONFIRM === true) {
    print('');
    print('='.repeat(70));
    print('自动确认模式：开始清理软删除记录');
    print('='.repeat(70));
    print('');
    
    let totalDeleted = 0;
    const deletedStats = {};
    
    collections.forEach(collectionName => {
        const collection = db.getCollection(collectionName);
        const count = collection.countDocuments({ deleted: 1 });
        
        if (count > 0) {
            // 执行删除
            const result = collection.deleteMany({ deleted: 1 });
            const deletedCount = result.deletedCount;
            
            deletedStats[collectionName] = deletedCount;
            totalDeleted += deletedCount;
            
            print(`✓ ${collectionName}: 删除 ${deletedCount} 条记录`);
        } else {
            print(`  ${collectionName}: 无需清理`);
        }
    });
    
    print('');
    print('='.repeat(70));
    print(`清理完成，共删除 ${totalDeleted} 条记录`);
    print('='.repeat(70));
    print('');
}
