<template>
  <view class="page-home">
    <!-- 1. 顶部红色搜索（沉浸式：预留状态栏高度） -->
    <view class="header-search-box">
      <view
        class="status-bar-spacer"
        :style="{ height: statusBarHeight + 'px' }"
      />
      <view class="search-row">
        <!-- 左上角：每日签到（LeetCode 式火焰两态：轮廓 → 燃烧） -->
        <view class="checkin-btn" :class="{ done: checkedIn }" @tap="onCheckin">
          <view class="checkin-icon">
            <image
              v-if="!checkedIn && CHECKIN_ICONS.outline"
              class="checkin-svg"
              :src="CHECKIN_ICONS.outline"
              mode="aspectFit"
            />
            <image
              v-else-if="checkedIn && CHECKIN_ICONS.burning"
              class="checkin-svg"
              :src="CHECKIN_ICONS.burning"
              mode="aspectFit"
            />
            <!-- SVG 未配置时的兜底：轮廓态用描边圆+「签」，燃烧态用 🔥 -->
            <text v-else class="checkin-fallback">{{
              checkedIn ? "🔥" : "签"
            }}</text>
          </view>
          <text class="checkin-count">{{ checkinLabel }}</text>
        </view>
        <view class="search-bar">
          <image
            class="icon-search"
            src="/static/ref/search-copy.svg"
            mode="aspectFit"
          />
          <input
            v-model="searchKeyword"
            class="search-input"
            placeholder="搜索内容/求助"
            placeholder-class="search-placeholder"
            confirm-type="search"
            @confirm="onSearch"
          />
          <text class="search-confirm" @tap="onSearch">搜索</text>
        </view>
      </view>
    </view>

    <!-- 2. 十大热帖：首页只露前 4，整卡可进完整榜单（无数据时整块隐藏） -->
    <view v-if="hotPosts.length" class="hot-posts-section" @tap="goHotList">
      <view class="hot-side-banner">
        <text class="hot-title">十大热帖</text>
        <text class="hot-arrow">›</text>
      </view>
      <view class="hot-main">
        <view class="hot-list">
          <view
            v-for="item in hotPosts"
            :key="item.id"
            class="hot-item"
            @tap.stop="goPost(item.id)"
          >
            <text class="rank-num" :class="rankClass(item.rank)">{{
              item.rank
            }}</text>
            <text class="hot-item-title">{{ item.title }}</text>
            <text v-if="item.isHot" class="hot-tag">热</text>
            <text class="read-count">{{ item.reads }}</text>
          </view>
        </view>
        <view class="hot-more">
          <text>查看完整榜单 ›</text>
        </view>
      </view>
    </view>

    <!-- 4. 广告位（可滑动轮播）；原金刚区已删（2026-09-01 客户反馈：与下方分类 Tab 重复） -->
    <swiper
      class="ad-swiper"
      indicator-dots
      indicator-color="rgba(255,255,255,0.45)"
      indicator-active-color="#ffffff"
      autoplay
      circular
      :interval="4000"
      :duration="500"
    >
      <swiper-item v-for="ad in adBanners" :key="ad.id" @tap="onAd(ad)">
        <!-- 有图 banner：图片铺满 + 底部渐变标题 -->
        <view v-if="ad.image_url" class="ad-slide ad-slide-img">
          <image class="ad-img" :src="ad.image_url" mode="aspectFill" />
          <view class="ad-img-mask">
            <view class="ad-text">
              <text class="ad-title">{{ ad.title }}</text>
              <text v-if="ad.desc" class="ad-desc">{{ ad.desc }}</text>
            </view>
          </view>
          <text v-if="ad.tag" class="ad-tag">{{ ad.tag }}</text>
        </view>
        <!-- 无图 banner：emoji + 渐变背景（mock fallback 同款样式） -->
        <view
          v-else
          class="ad-slide"
          :style="{
            background: ad.bg || 'linear-gradient(135deg, #ef8a97, #f6b8c0)',
          }"
        >
          <text class="ad-emoji">{{ ad.emoji || "📢" }}</text>
          <view class="ad-text">
            <text class="ad-title">{{ ad.title }}</text>
            <text class="ad-desc">{{ ad.desc }}</text>
          </view>
          <text class="ad-tag">{{ ad.tag }}</text>
        </view>
      </swiper-item>
    </swiper>

    <!-- 6. 吸顶分类 Tab -->
    <view class="tab-bar-sticky">
      <scroll-view class="tab-scroll" scroll-x :show-scrollbar="false">
        <view
          v-for="(t, idx) in TABS"
          :key="idx"
          class="tab-item-wrap"
        >
          <view v-if="idx === 4" class="tab-sep" />
          <view
            class="tab-item"
            :class="{ active: currentTab === idx, 'tab-category': t.kind === 'category' }"
            @tap="switchTab(idx)"
          >
            {{ t.label }}
          </view>
        </view>
      </scroll-view>
    </view>

    <!-- 7. 信息流 -->
    <view class="feed-list">
      <view v-if="loadingFeeds && posts.length === 0" class="skeleton-list">
        <SkeletonCard v-for="i in 4" :key="i" />
      </view>
      <view v-else-if="posts.length === 0" class="feed-tip"
        ><text>暂无内容，下拉刷新或去发布</text></view
      >
      <FeedCard
        v-for="p in posts"
        :key="p.id"
        :post="p"
        @detail="goPost(p.id)"
      />
      <view v-if="posts.length > 0" class="feed-foot">
        <text v-if="loadingFeeds">加载中…</text>
        <text v-else-if="hasMore">上拉加载更多</text>
        <text v-else>没有更多了</text>
      </view>
    </view>

    <TabBar :current="0" />
  </view>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { onShow, onPullDownRefresh, onReachBottom } from "@dcloudio/uni-app";
import FeedCard from "@/components/feed-card.vue";
import TabBar from "@/components/tab-bar.vue";
import { AD_BANNERS, POST_CATEGORIES } from "@/utils/mock";
import type { PostBrief } from "@/types/api";
import { getPosts, getHotPosts, getFeaturedPosts, getFollowingFeed } from "@/api/posts";
import { getBanners, type BannerItem } from "@/api/banner";
import { doCheckin, getCheckinStatus } from "@/api/checkin";
import { tokenStorage } from "@/utils/storage";

// 顶部 tab：对齐参考稿（精选/最新/二手/失物）+ 保留功能入口（关注/精华）
// 分类完整清单仍由 POST_CATEGORIES 提供（发布页选择器用），此处只是首页瘦身
const TABS: Array<{ label: string; mode: string; kind: 'mode' | 'category' }> = [
  { label: "精选", mode: "all", kind: "mode" }, // 热度时间衰减推荐
  { label: "最新", mode: "latest", kind: "mode" }, // 纯时间序（order=time）
  { label: "关注", mode: "following", kind: "mode" },
  { label: "精华", mode: "featured", kind: "mode" },
  { label: "二手", mode: "二手市场", kind: "category" },
  { label: "失物", mode: "失物招领", kind: "category" },
];
const currentTab = ref(0);
// feed 模式：'all'(推荐) | 'following'(关注) | <分类名>
const feedMode = ref<string>("all");
interface HotItem {
  id: number;
  rank: number;
  title: string;
  isHot: boolean;
  reads: string;
}
const hotPosts = ref<HotItem[]>([]);
// 广告轮播：后端下发优先，失败/未配置时 fallback 到 mock（运营未配不白屏）
const adBanners = ref<(BannerItem & { bg?: string; emoji?: string })[]>([
  ...AD_BANNERS,
]);

const loadBanners = async () => {
  try {
    const items = await getBanners();
    if (items.length) adBanners.value = items;
  } catch {
    /* 后端不可用时保留 fallback */
  }
};
// 每日签到（收益体系定稿后扩展奖励弹窗）
/**
 * 火焰图标更换位（LeetCode 式两态）：
 * 1. 把两张图放进 src/static/checkin/（任意文件名，建议正方形）
 * 2. 把下面两行路径改成你的文件并解开注释，保存即生效（HMR 秒级热更）
 * 注意：SVG 在 H5 没问题；微信小程序真机不渲染 SVG，上真机请换 PNG（路径后缀改 .png 即可）
 */
const CHECKIN_ICONS: { outline?: string; burning?: string } = {
  // outline: "/static/checkin/flame-outline.svg", // 未签到：火焰轮廓（线条稿）
  // burning: "/static/checkin/flame-burning.svg", // 已签到：燃烧的火焰（填充稿）
};

const checkedIn = ref(false);
const streakDays = ref(0);
// 右侧数字：已签=当前连签；未签但昨天的连签还在=显示它（提醒别断签）；全新=「签到」
const checkinLabel = computed(() =>
  checkedIn.value || streakDays.value > 0 ? String(streakDays.value) : "签到"
);
const loadCheckin = async () => {
  if (!tokenStorage.isLoggedIn()) return;
  try {
    const st = await getCheckinStatus();
    checkedIn.value = st.today_checked;
    streakDays.value = st.streak_days;
  } catch { /* 静默 */ }
};
const onCheckin = async () => {
  if (!tokenStorage.isLoggedIn()) {
    uni.showToast({ title: "登录后才能签到", icon: "none" });
    return;
  }
  if (checkedIn.value) {
    uni.showToast({ title: `今天已签到，连签 ${streakDays.value} 天`, icon: "none" });
    return;
  }
  try {
    const r = await doCheckin();
    checkedIn.value = true;
    streakDays.value = r.streak_days;
    uni.showToast({
      title: r.already ? `今天已签到，连签 ${r.streak_days} 天` : `签到成功！连签 ${r.streak_days} 天`,
      icon: "none",
    });
  } catch (e) {
    uni.showToast({ title: (e as Error).message || "签到失败", icon: "none" });
  }
};

const posts = ref<PostBrief[]>([]);
const loadingFeeds = ref(false);
const nextCursor = ref<number | null>(null);
const hasMore = ref(false);
const searchKeyword = ref("");

// 沉浸式头部：状态栏高度（custom 导航栏后内容会顶到状态栏，需让出空间）
const statusBarHeight = uni.getSystemInfoSync().statusBarHeight || 0;

const loadFeeds = async (refresh = false) => {
  if (loadingFeeds.value) return;
  loadingFeeds.value = true;
  try {
    const cursor = refresh ? undefined : nextCursor.value;
    let res;
    if (feedMode.value === "following")
      res = await getFollowingFeed(cursor ?? undefined);
    else if (feedMode.value === "featured")
      res = await getFeaturedPosts(cursor ?? undefined);
    else if (feedMode.value === "latest")
      res = await getPosts(cursor ?? undefined, undefined, undefined, "time");
    else if (feedMode.value !== "all")
      res = await getPosts(cursor ?? undefined, undefined, feedMode.value);
    else res = await getPosts(cursor ?? undefined);
    if (refresh) posts.value = res.items;
    else posts.value.push(...res.items);
    nextCursor.value = res.next_cursor;
    hasMore.value = res.has_more;
  } catch (e) {
    uni.showToast({ title: (e as Error).message || "加载失败", icon: "none" });
  } finally {
    loadingFeeds.value = false;
  }
};

onPullDownRefresh(async () => {
  await loadFeeds(true);
  uni.stopPullDownRefresh();
});

onReachBottom(() => {
  if (hasMore.value && !loadingFeeds.value) loadFeeds(false);
});

const HOT_TITLE_MAX = 30; // 榜单标题截断长度（rpx 布局按单行省略，防长文挤压）
const HOT_TAG_MIN_LIKES = 3; // 「热」标门槛：赞或评论 ≥3，避免 1 赞也挂热

const loadHot = async () => {
  try {
    // 首页只露前 4 名（完整十强在二级页 pages/hot/index）
    const list = await getHotPosts(4);
    hotPosts.value = list.map((p, i) => ({
      id: p.id,
      rank: i + 1,
      // 正文首行做标题，超长截断
      title: (() => {
        const firstLine = (p.content || "").split("\n").find((s) => s.trim()) || "（无文字）";
        return firstLine.length > HOT_TITLE_MAX
          ? firstLine.slice(0, HOT_TITLE_MAX) + "…"
          : firstLine;
      })(),
      isHot:
        (p.like_count || 0) >= HOT_TAG_MIN_LIKES ||
        (p.comment_count || 0) >= HOT_TAG_MIN_LIKES,
      reads: `${p.view_count || 0} 浏览`,
    }));
  } catch {
    /* 热帖非关键，失败静默（整块由 v-if 隐藏） */
  }
};

const goHotList = () => uni.navigateTo({ url: "/pages/hot/index" });

onShow(() => {
  loadFeeds(true);
  loadHot();
  loadBanners();
  loadCheckin();
});

const rankClass = (rank: number) => `rank-${rank}`;

const onSearch = () => {
  const q = searchKeyword.value.trim();
  uni.navigateTo({
    url: q
      ? `/pages/search/index?q=${encodeURIComponent(q)}`
      : "/pages/search/index",
  });
};
const toHttp = (u: string) => (/^https?:\/\//i.test(u) ? u : `https://${u}`)

const onAd = (ad: BannerItem) => {
  if (ad.post_id) {
    uni.navigateTo({ url: `/pages/post-detail/index?id=${ad.post_id}` });
    return
  }
  if (ad.activity_id) {
    uni.navigateTo({ url: `/pages/activity/index?id=${ad.activity_id}` });
    return
  }
  if (ad.link_url) {
    const link = toHttp(ad.link_url)
    // #ifdef H5
    // 外链直接交给系统浏览器打开：第三方站点若禁止 iframe 嵌入，网页端无法强制内嵌显示
    const win = window.open(link, '_blank', 'noopener,noreferrer')
    if (!win) window.location.href = link
    // #endif
    // #ifndef H5
    uni.navigateTo({ url: `/pages/webview/index?url=${encodeURIComponent(link)}` })
    // #endif
  }
};

const goPost = (id: number) => {
  uni.navigateTo({ url: `/pages/post-detail/index?id=${id}` });
};

const switchTab = (idx: number) => {
  const t = TABS[idx];
  if (t.mode === "following" && !tokenStorage.isLoggedIn()) {
    uni.showToast({ title: "请先登录后查看关注", icon: "none" });
    return;
  }
  feedMode.value = t.mode;
  currentTab.value = idx;
  loadFeeds(true);
};
</script>

<style scoped>
.page-home {
  min-height: 100vh;
  background-color: var(--bg-page);
  padding-bottom: 40rpx;
}

/* 1. 红色头部（沉浸式） */
.header-search-box {
  background-color: var(--brand-red);
  display: flex;
  flex-direction: column;
}

.status-bar-spacer {
  width: 100%;
}

.search-row {
  height: 108rpx; /* 头部厚度（不含状态栏） */
  padding: 0 24rpx;
  display: flex;
  align-items: center;
}

/* 左上角火焰签到（LeetCode 式两态）：未签=描边幽灵胶囊，已签=白底实心 */
.checkin-btn {
  flex-shrink: 0;
  height: 64rpx;
  padding: 0 18rpx;
  margin-right: 20rpx;
  border: 2rpx solid rgba(255, 255, 255, 0.9);
  border-radius: 34rpx;
  display: flex;
  align-items: center;
  gap: 10rpx;
}
.checkin-btn.done {
  background-color: #ffffff;
  border-color: #ffffff;
  box-shadow: 0 2rpx 12rpx rgba(226, 109, 125, 0.18);
}

.checkin-icon {
  width: 36rpx;
  height: 36rpx;
  display: flex;
  align-items: center;
  justify-content: center;
}
.checkin-svg {
  width: 36rpx;
  height: 36rpx;
}
/* 兜底字形：轮廓态「签」（描边风格），燃烧态 🔥 */
.checkin-fallback {
  font-size: 26rpx;
  line-height: 1;
  color: #ffffff;
}
.checkin-btn.done .checkin-fallback {
  font-size: 30rpx;
}

/* 右侧连签数字 */
.checkin-count {
  font-size: 24rpx;
  font-weight: 700;
  color: #ffffff;
  line-height: 1;
}
.checkin-btn.done .checkin-count {
  color: var(--brand-red-dark);
}

.search-bar {
  flex: 1;
  min-width: 0;
  height: 64rpx;
  background-color: #ffffff;
  border-radius: 32rpx;
  padding: 0 26rpx;
  display: flex;
  align-items: center;
  box-shadow: 0 2rpx 12rpx rgba(226, 109, 125, 0.12);
}

.icon-search {
  width: 28rpx;
  height: 28rpx;
  flex-shrink: 0;
}

.search-input {
  flex: 1;
  font-size: 26rpx;
  margin-left: 14rpx;
  color: var(--text-1);
}

.search-placeholder {
  color: #b9bcc2;
}

.search-confirm {
  font-size: 26rpx;
  color: var(--brand-red);
  padding-left: 20rpx;
  border-left: 1rpx solid #eef0f3;
}

/* 2. 十大热帖（原"搭乘UFO"通知栏已删，2026-09-01 客户反馈） */
.hot-posts-section {
  background-color: #ffffff;
  margin: 20rpx 24rpx 24rpx;
  border-radius: var(--radius-card);
  padding: 24rpx;
  display: flex;
  align-items: stretch; /* 侧边徽章跟随 10 行列表高度 */
}

.hot-side-banner {
  width: 150rpx;
  min-height: 150rpx; /* 兜底：短列表时色块至少装得下"十大热帖"标题，防文字溢出 */
  background: linear-gradient(135deg, #e8848f, #f6b8c0);
  border-radius: 16rpx;
  justify-content: center;
  align-items: center;
  display: flex;
  flex-direction: column;
  color: #ffffff;
  flex-shrink: 0;
}

.hot-title {
  font-size: 30rpx;
  font-weight: bold;
  text-align: center;
  width: 80rpx;
  line-height: 1.3;
}

.hot-arrow {
  font-size: 28rpx;
  margin-top: 6rpx;
  opacity: 0.8;
}

/* 右侧主体：前 4 列表 + 「查看完整榜单」脚注 */
.hot-main {
  flex: 1;
  min-width: 0; /* 关键：允许整列收缩，否则被最长行撑爆，热标/浏览数被顶出屏 */
  overflow: hidden;
  margin-left: 24rpx;
  display: flex;
  flex-direction: column;
}

.hot-list {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-around;
}

.hot-more {
  margin-top: 14rpx;
  padding-top: 12rpx;
  border-top: 1rpx solid #f5f5f6;
  display: flex;
  justify-content: center;
}

.hot-more text {
  font-size: 22rpx;
  color: var(--text-3);
}

.hot-item {
  display: flex;
  align-items: center;
  font-size: 24rpx;
  line-height: 1.6;
  padding: 2rpx 0;
}

.rank-num {
  font-weight: bold;
  font-style: italic;
  margin-right: 12rpx;
  width: 30rpx;
  flex-shrink: 0;
  color: var(--text-3);
}

.rank-1 {
  color: var(--brand-red-dark);
}
.rank-2 {
  color: #e8a23f;
}
.rank-3 {
  color: #d9b23f;
}

.hot-item-title {
  flex: 1;
  min-width: 0; /* flex 子项默认 min-width:auto，长文本会撑爆行容器，必须允许收缩 */
  color: var(--text-1);
  font-size: 26rpx;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hot-tag {
  background-color: var(--brand-red-dark);
  color: #ffffff;
  font-size: 18rpx;
  padding: 2rpx 8rpx;
  border-radius: 6rpx;
  margin-left: 10rpx;
  flex-shrink: 0;
}

.read-count {
  font-size: 22rpx;
  color: var(--text-3);
  margin-left: 16rpx;
  flex-shrink: 0;
}

/* 4. 广告位轮播（原金刚区样式已随功能删除） */
.ad-swiper {
  height: 180rpx;
  margin: 24rpx 24rpx 24rpx; /* 金刚区删除后由顶部留白接管 */
}

.ad-slide {
  height: 100%;
  border-radius: var(--radius-card);
  padding: 0 28rpx;
  display: flex;
  align-items: center;
  position: relative;
  overflow: hidden;
}

/* 有图 banner：图片铺满 */
.ad-slide-img {
  padding: 0;
}
.ad-img {
  position: absolute;
  left: 0;
  top: 0;
  width: 100%;
  height: 100%;
}
.ad-img-mask {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 24rpx 28rpx 16rpx;
  background: linear-gradient(180deg, transparent, rgba(0, 0, 0, 0.55));
  display: flex;
  align-items: flex-end;
}
.ad-slide-img .ad-text {
  flex: 1;
}

.ad-emoji {
  font-size: 64rpx;
  margin-right: 22rpx;
}

.ad-text {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.ad-title {
  color: #ffffff;
  font-size: 30rpx;
  font-weight: bold;
}

.ad-desc {
  color: rgba(255, 255, 255, 0.88);
  font-size: 22rpx;
  margin-top: 6rpx;
}

.ad-tag {
  position: absolute;
  top: 16rpx;
  right: 20rpx;
  color: rgba(255, 255, 255, 0.85);
  font-size: 18rpx;
  border: 1rpx solid rgba(255, 255, 255, 0.6);
  padding: 2rpx 12rpx;
  border-radius: 16rpx;
}

/* 6. 吸顶 Tab */
.tab-bar-sticky {
  position: sticky;
  top: 0;
  z-index: 10;
  background-color: var(--bg-page);
}

.tab-scroll {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  white-space: nowrap;
  padding: 16rpx 24rpx;
}

.tab-item-wrap {
  display: inline-flex;
  align-items: center;
}

.tab-sep {
  width: 2rpx;
  height: 30rpx;
  background: #e9ebee;
  margin: 0 20rpx;
}

.tab-item {
  display: inline-block;
  font-size: 28rpx;
  color: var(--text-2);
  margin-right: 36rpx;
  padding-bottom: 12rpx;
}

.tab-item.active {
  color: var(--text-1);
  font-weight: bold;
  border-bottom: 6rpx solid var(--brand-red);
}

.tab-item.tab-category {
  margin-right: 16rpx;
  padding: 8rpx 20rpx;
  border-radius: 999rpx;
  background: #ffffff;
  border: 1rpx solid #f0e4e7;
  color: var(--text-2);
}

.tab-item.tab-category.active {
  background: var(--brand-red);
  border-color: var(--brand-red);
  color: #ffffff;
  border-bottom: 1rpx solid var(--brand-red);
}

/* 7. 信息流 */
.feed-list {
  padding: 0 24rpx;
}
.feed-tip {
  text-align: center;
  padding: 60rpx 0;
  color: var(--text-3);
  font-size: 26rpx;
}
.feed-foot {
  text-align: center;
  padding: 32rpx 0;
  color: var(--text-3);
  font-size: 24rpx;
}
</style>
